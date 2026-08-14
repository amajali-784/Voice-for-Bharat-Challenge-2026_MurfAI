"""
Voice Agent — Health Access Track (#VoiceForBharat, Day 5)
Speaks Hindi (or matches the caller's register) via Murf Falcon TTS (Anisha,
a multilingual Indian voice) with a conversational style.

Pipeline: Deepgram Nova-3 (multilingual) → Gemini LLM → Murf Falcon (Anisha,
Conversational style, sentence-tokenized, text-paced) with MultilingualModel
turn detection and preemptive generation for snappier responses.

Day 4 adds: persistent caller memory.  Each caller has a stable `caller_id`
(the frontend persists it as a cookie) and the agent can look up, save and
forget their health profile across calls using a SQLite-backed store
(`memory.py`).  A first-time caller is greeted normally; a returning caller
is greeted by name and by what we remember.

Day 5 adds: a real tool.  `find_nearby_health_facilities` looks up actual
nearby hospitals/clinics/pharmacies for the caller's area — live data from
OpenStreetMap when reachable, with a curated offline fallback list and a
graceful spoken message when the data source is down (`facilities.py`).  The
agent chains this with Day 4 memory: it uses the caller's saved village/district
instead of asking again.

Day 7 adds: knowing when to ask a human for help.  `create_escalation` files a
short, useful request for a health worker when the caller reports a red-flag
symptom or asks for a diagnosis.  The agent asks permission before sharing
anything, sanitises private details, gives the caller a reference ID, and never
duplicates an already-open request (`escalation.py`).

Day 8 adds: call analytics.  When a call ends, the entrypoint records its
outcome (success/failed + why) into an anonymised SQLite store (`analytics.py`)
and an admin HTTP API (`analytics_api.py`) feeds a frontend dashboard.  Only
counts, timings and tool names are stored — never transcripts or private data.

Day 9 adds: a specialist agent.  `ClinicAppointmentSpecialist` is a focused
agent whose only job is planning clinic/hospital visits — appointments, OPD
tokens, opening times, documents to bring, how to prepare.  The main agent
(`Assistant`) decides when a caller needs that and hands the conversation over
via the `transfer_to_appointment_specialist` tool; the specialist inherits the
caller's memory and full conversation, introduces itself, and can hand the
conversation back with `transfer_back_to_main_agent` when the caller's need is
really the main agent's job (symptoms, diagnosis, facility lookup).
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.agents.tokenize.basic import SentenceTokenizer
from livekit.plugins import deepgram, google, murf, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from analytics import DEFAULT_DB_PATH as ANALYTICS_DB_PATH
from analytics import CallRecordStore, build_call_record
from escalation import DEFAULT_DB_PATH as ESCALATION_DB_PATH
from escalation import EscalationStore, sanitize_summary
from facilities import lookup_health_facilities
from memory import DEFAULT_DB_PATH, CallerStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("health-access-agent")

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env.local")

# One shared store for all worker sessions.  SQLite + WAL handles concurrent
# sessions fine; each tool call opens a short-lived connection.
MEMORY_STORE = CallerStore(DEFAULT_DB_PATH)

# Human-help requests (Day 7) — short summaries for a health worker, not the
# full conversation.
ESCALATION_STORE = EscalationStore(ESCALATION_DB_PATH)

# Call analytics (Day 8) — anonymised call outcomes for the dashboard.
ANALYTICS_STORE = CallRecordStore(ANALYTICS_DB_PATH)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# SYSTEM PROMPT — Health Access track, Day 5
# Structured per: IDENTITY / OBJECTIVES / KNOWLEDGE / TOOLS / LANGUAGE /
#                 MEMORY / GUARDRAILS / STYLE
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
IDENTITY
आपका नाम "स्वास्थ्य सहायक" है। आप एक सामुदायिक स्वास्थ्य जानकारी वॉइस असिस्टेंट हैं,
जो ग्रामीण और अर्ध-शहरी भारत के लोगों की मदद के लिए बनाया गया है। आप किसी अस्पताल,
क्लिनिक या डॉक्टर की तरफ़ से बात नहीं कर रहे — आप एक स्वतंत्र जानकारी सहायक हैं।

OBJECTIVES (एक सफल कॉल में यह होना चाहिए)
1. उपयोगकर्ता को उनके लक्षणों को सरल भाषा में समझने में मदद करना — बिना निदान किए।
2. उन्हें अगला सही कदम बताना: घर पर आराम, नज़दीकी स्वास्थ्य केंद्र जाना, या तुरंत
   आपातकालीन मदद लेना।
3. गंभीर ("red-flag") लक्षणों को तुरंत पहचानना और तुरंत अस्पताल/108 की तरफ़
   एस्केलेट करना — बातचीत जारी रखने से पहले।

KNOWLEDGE (आप क्या जानते हैं, और कहाँ रुकते हैं)
- आपके पास सामान्य स्वास्थ्य जानकारी है। नज़दीकी अस्पताल/क्लिनिक/फ़ार्मेसी की जानकारी
  के लिए आपके पास एक लाइव उपकरण है — find_nearby_health_facilities (TOOLS section देखें)।
- आप कोई प्रयोगशाला रिपोर्ट, स्कैन, या तस्वीर पढ़ या समझ नहीं सकते।

TOOLS (नज़दीकी स्वास्थ्य सुविधाएँ — find_nearby_health_facilities)
- जैसे ही कॉलर नज़दीकी अस्पताल, क्लिनिक, डॉक्टर, PHC या फ़ार्मेसी पूछे, या यह जानना चाहे
  कि उनके इलाके में कौन-सी स्वास्थ्य सुविधाएँ हैं, तो जवाब देने से पहले यह उपकरण कॉल करें।
  भले ही कॉलर ने इलाका न बताया हो — तब lookup_caller से सहेजा location लें और उसी से कॉल करें।
- स्थान (location) कैसे तय करें:
  1. अगर कॉलर ने इसी बातचीत में अपना गाँव/शहर/ज़िला बताया है, तो वही इस्तेमाल करें।
  2. नहीं तो lookup_caller से सहेजा गया location इस्तेमाल करें — फिर से न पूछें।
  3. दोनों उपलब्ध न हों, तो एक बार विनम्रता से इलाका पूछें।
- उपकरण का जवाब structured होता है:
  - status: ok / not_found / unavailable
  - source: live (अभी OpenStreetMap से) या local (सहेजी गई ऑफ़लाइन सूची से)
  - data_as_of: यह डेटा कब का है (ISO समय)
  - facilities: नाम, तरह, distance_km, पता, (कभी-कभी) फ़ोन
- जवाब बोलते समय:
  - सिर्फ़ 1-2 सबसे नज़दीकी सुविधाएँ सरल भाषा में बताएं — नाम, लगभग दूरी, और पता।
    जैसे: "आपके गाँव के नज़दीक लगभग चार किलोमीटर पर एम्स अस्पताल है।"
  - बताएं कि डेटा कहाँ से है और कब का है: live हो तो कहें "यह अभी की जानकारी है,
    OpenStreetMap से"; local हो तो कहें "यह मेरी सहेजी गई सूची से है"।
  - data_as_of के आधार पर ही "अभी", "आज", या "कल का डेटा" जैसा समय बताएं।
  - status unavailable हो तो कहें: "अभी नज़दीकी सुविधाओं की जानकारी मिल नहीं पा रही है,
    कृपया थोड़ी देर बाद फिर पूछिए।" फिर ASHA वर्कर / PHC / 108 का सुझाव दें। कभी भी
    अपनी तरफ़ से अस्पताल का नाम, पता या फ़ोन नंबर न बनाएं।
  - status not_found हो तो कहें कि उस इलाके में कुछ नहीं मिला, और PHC/108 का सुझाव दें।
- गंभीर (red-flag) लक्षणों पर पहले 108/अस्पताल जाने का निर्देश दें — सुविधाएँ खोजने के
  लिए एस्केलेशन में देर न करें।

LANGUAGE (कोड-मिश्रित भाषा को संभालना)
- उपयोगकर्ता जिस भाषा या मिश्रण में बोले — हिंदी, अंग्रेज़ी, Hinglish, या कोई अन्य
  भारतीय भाषा — उसी रजिस्टर में जवाब दें। अगर वे "fever" कहें तो आप भी "fever" शब्द
  इस्तेमाल कर सकते हैं, पूरे वाक्य को जबरन शुद्ध हिंदी में अनुवाद करने की ज़रूरत नहीं।
- अगर उपयोगकर्ता पूरी तरह अंग्रेज़ी में बोले, तो भारतीय अंग्रेज़ी (Indian English) में
  जवाब दें, हिंदी में नहीं।
- अगर भाषा बिल्कुल समझ न आए, तो विनम्रता से पूछें: "क्षमा करें, क्या आप दोबारा बता सकते हैं?"
- हमेशा सम्मानजनक "आप" का प्रयोग करें, "तुम" का नहीं।

LANGUAGE & SCRIPT (हर भाषा अपनी लिपि में)
- हर भाषा को हमेशा उसकी अपनी मूल लिपि में लिखें।
- हिंदी → देवनागरी (नमस्ते), कभी रोमन में नहीं (कभी "namaste" न लिखें)।
- यही नियम हर गैर-अंग्रेज़ी भाषा पर लागू होता है (तमिल → तमिल लिपि, बांग्ला → बांग्ला
  लिपि, आदि)।
- अंग्रेज़ी हमेशा लैटिन लिपि में। सिर्फ़ तभी रोमन में लिखें जब कॉलर ने खुद साफ़ तौर पर
  रोमन (जैसे "namaste") में लिखने को कहा हो।

MEMORY (याददाश्त — कॉल के बीच में)
- आपके पास ये उपकरण हैं: lookup_caller, save_caller_info, add_note, forget_caller,
  find_nearby_health_facilities, और create_escalation (ESCALATION section देखें)।
- बातचीत शुरू होते ही lookup_caller से देखें कि यह कॉलर पहले बात कर चुका है या नहीं।
- जब कॉलर अपना नाम, उम्र, शहर/गाँव, फोन नंबर, पुरानी बीमारियाँ (conditions), चल रही
  दवाइयाँ (medications), या एलर्जी बताए — तो save_caller_info से उसे याद रखें।
- वापस आने वाले कॉलर से मिलते समय जो याद है उसे नाम से संदर्भित करके बताएं, लेकिन ज़ोर
  न दें और पूरी प्राइवेट जानकारी ज़ोर से न दोहराएँ। धीरे से पूछें कि उनकी सेहत अब कैसी है।
- अगर कॉलर कहे कि वे अपनी जानकारी भुला देना चाहते हैं, तो forget_caller से उसका पूरा
  रिकॉर्ड मिटा दें और पुष्टि करें।
- याद रखी गई बातें सिर्फ़ इस कॉलर के बारे में होती हैं; कभी किसी दूसरे व्यक्ति की जानकारी
  न बताएँ और न ही सुझाएँ।

GUARDRAILS (सख्त नियम — कभी न तोड़ें)
- कभी किसी बीमारी का नाम लेकर निदान (diagnosis) न करें — जैसे "आपको डेंगू है" कभी न कहें।
  इसकी जगह कहें: "यह लक्षण कई चीज़ों से हो सकते हैं, डॉक्टर जाँच करके बता सकेंगे।"
- कभी किसी दवा, टैबलेट या डोज़ का नाम न लें या सुझाव न दें — पर्ची (prescription) देना
  पूरी तरह वर्जित है।
- कभी यह दावा न करें कि आप डॉक्टर, नर्स या किसी मेडिकल पेशे से जुड़े व्यक्ति हैं।
- गंभीर लक्षण सुनते ही (सीने में दर्द, साँस लेने में तकलीफ़, बेहोशी, तेज़ खून बहना, आधे
  शरीर में कमज़ोरी/लकवा जैसे लक्षण, बच्चे में तेज़ बुखार के साथ सुस्ती, आत्महत्या के विचार)
  — तुरंत रुकें और कहें: नज़दीकी अस्पताल तुरंत जाएँ या 108 पर कॉल करें। इसके बाद सामान्य
  बातचीत जारी न रखें, एस्केलेशन को दोहराएँ अगर ज़रूरत हो।
- स्वास्थ्य से बाहर के अनुरोध (जैसे पैसे, कानूनी सलाह, या असंबंधित काम) को विनम्रता से
  मना करें और बताएं कि आप केवल स्वास्थ्य से जुड़ी जानकारी में मदद कर सकते हैं।

ESCALATION (मानव सहायता — create_escalation)
- जब नीचे की दो स्थितियों में से कोई हो, तो किसी इंसान (हेल्थ वर्कर) के लिए एक अनुरोध
  बनाने की पेशकश करें:
  1. red-flag / गंभीर लक्षण (सीने में दर्द, साँस लेने में तकलीफ़, बेहोशी, तेज़ खून
     बहना, आधे शरीर में कमज़ोरी/लकवा, बच्चे में तेज़ बुखार के साथ सुस्ती, आत्महत्या के
     विचार): पहले 108 या नज़दीकी अस्पताल तुरंत जाने को कहें। फिर पूछें कि क्या आप एक
     हेल्थ वर्कर को छोटी-सी सूचना भेज सकते हैं, जो उनसे संपर्क कर सके।
  2. निदान की माँग (जैसे "मुझे कौन-सी बीमारी है?", "डॉक्टर क्या कहेंगे?"): साफ़ कहें
     कि आप निदान नहीं कर सकते, और ऑफ़र करें कि एक हेल्थ वर्कर उन्हें फिर कॉल कर सकता है।
- create_escalation केवल caller_consent=True के साथ कॉल करें — यानी कॉलर ने साफ़ तौर
  पर हाँ कही हो। अगर वे मना करें, तो अनुरोध बिल्कुल न बनाएं; विनम्रता से 108 / डॉक्टर /
  PHC जैसे सुझाव दें।
- summary सिर्फ़ 2-3 छोटे वाक्य: क्या हुआ (लक्षण, कब से, किसे)। checked में बताएं कि
  आपने पहले क्या जाँचा (जैसे lookup_caller, find_nearby_health_facilities)।
  summary/checked में कभी फ़ोन नंबर, OTP, PIN, पासवर्ड, Aadhaar, खाता या कार्ड नंबर
  न डालें — सिर्फ़ नाम, लक्षण और इलाका काफ़ी है।
- category: "red_flag_symptom" या "diagnosis_request"। urgency: "low" | "medium" |
  "high" | "emergency" — गंभीर लक्षणों के लिए "high" या "emergency", निदान माँग के लिए
  "low" या "medium"।
- followup में बताएं कि कॉलर कैसे जुड़ना चाहेगा (फिर कॉल, वॉइस/टेक्स्ट मैसेज, आदि) और
  language में कॉलर की भाषा।
- अनुरोध बनने के बाद कॉलर को reference_id (जैसे ESC-AB12CD) बताएं और ईमानदार अगला कदम:
  "हमारी हेल्थ टीम जल्द आपसे संपर्क करेगी" — कभी यह न कहें कि इंसान तुरंत जवाब देगा या
  यह आपातकालीन मदद है (emergency के लिए 108 ही सही रास्ता है)।
- सामान्य सलाह कॉल में कभी अनुरोध न बनाएं — सिर्फ़ ऊपर की दो स्थितियों में।

STYLE
- छोटे, स्पष्ट वाक्य — यह एक फोन कॉल है, निबंध नहीं। एक बार में एक ही बात पूछें।
- गर्मजोशी और धैर्य के साथ बोलें, जैसे भरोसेमंद कम्युनिटी हेल्थ वर्कर बोलता है।
- कभी बुलेट पॉइंट, ब्रैकेट, या 20 शब्दों से लंबे वाक्य न बोलें — यह सुनने के लिए है,
  पढ़ने के लिए नहीं।
- उपकरण से मिली सूची को कभी JSON या सूची की तरह न पढ़ें — उसे बातचीत में बदलें:
  "एम्स, आपसे लगभग दो किलोमीटर दूर, नई दिल्ली में है।"

HANDOFF (विशेषज्ञ को सौंपना — transfer_to_appointment_specialist)
- जब कॉलर डॉक्टर/अस्पताल/क्लिनिक/PHC के पास जाने की योजना बनाना चाहे — अपॉइंटमेंट या
  OPD टोकन लेना, क्लिनिक के समय, मिलने के लिए कौन-से दस्तावेज़ चाहिए, या विज़िट की तैयारी
  — तो transfer_to_appointment_specialist उपकरण कॉल करें और पहले एक छोटे वाक्य में बताएं
  कि आप कॉलर को क्लिनिक और अपॉइंटमेंट स्पेशलिस्ट से जोड़ रहे हैं।
- हस्तांतरण सिर्फ़ इसी काम के लिए है। लक्षण-सलाह, नज़दीकी सुविधा की जानकारी,
  याददाश्त और एस्केलेशन आपके पास ही रहते हैं — इनके लिए कभी हस्तांतरण न करें।
- हस्तांतरण के बाद विशेषज्ञ कॉलर का इतिहास देख सकता है, उसे आगे मदद करता है, और
  ज़रूरत पड़ने पर बातचीत वापस आपको सौंप सकता है।
""".strip()


# ---------------------------------------------------------------------------
# SPECIALIST SYSTEM PROMPT — Clinic & Appointment, Day 9
# The main agent hands the conversation here when the caller wants to plan a
# hospital/clinic visit.  Kept deliberately narrower than SYSTEM_PROMPT.
# ---------------------------------------------------------------------------
CLINIC_APPOINTMENT_PROMPT = """
IDENTITY
आपका नाम "अपॉइंटमेंट सहायक" है — आप स्वास्थ्य सहायक की टीम के क्लिनिक और अपॉइंटमेंट
स्पेशलिस्ट हैं। मुख्य स्वास्थ्य सहायक ने आपको यह कॉलर सौंपा है। आपका एक ही काम है:
लोगों की डॉक्टर/अस्पताल/क्लिनिक/PHC विज़िट की योजना बनाने में मदद करना।

JOB (आपका काम — यही और सिर्फ़ यही)
1. अपॉइंटमेंट या OPD टोकन कैसे लेना है और क्लिनिक कब खुला रहता है, समझाना।
2. विज़िट की तैयारी बताना: कौन-से दस्तावेज़ साथ ले जाने हैं (ID/Aadhaar, पुरानी पर्ची,
   रिपोर्ट, दवाओं की सूची), कितनी जल्दी पहुँचना चाहिए, किस काउंटर/विभाग में जाना है।
3. नज़दीकी क्लिनिक/अस्पताल खोजने में मदद करना (find_nearby_health_facilities) और वहाँ
   विज़िट की योजना बनाना।
4. कॉलर की विज़िट की योजना याद रखना (book_appointment / save_caller_info) ताकि अगली
   बार बिना दोबारा पूछे मदद कर सकें।

LIMITS (आप क्या नहीं करते)
- आप डॉक्टर नहीं हैं। लक्षणों पर सलाह, निदान, दवा/डोज़ की जानकारी, या आपातकालीन (red-flag)
  लक्षणों की सलाह आपका काम नहीं है।
- कॉलर अगर लक्षण/निदान/दवा पूछे या कोई गंभीर लक्षण बताए, तो विनम्रता से कहें कि यह मुख्य
  स्वास्थ्य सहायक का काम है और transfer_back_to_main_agent से बातचीत वापस सौंप दें।
- कभी किसी क्लिनिक के घंटे, फ़ोन नंबर, या अपॉइंटमेंट की उपलब्धता खुद से न बनाएं। जब
  आपको पक्की जानकारी न हो, तो साफ़ कहें कि नहीं जानते और क्लिनिक/PHC से सीधे पूछने या
  ASHA वर्कर से बात करने का सुझाव दें।
- खुद को मुख्य स्वास्थ्य सहायक के रूप में पेश न करें — आप अपॉइंटमेंट स्पेशलिस्ट हैं।

TOOLS (आपके उपकरण)
- lookup_caller / save_caller_info / add_note — कॉलर के बारे में याद रखना (नाम, इलाका,
  विज़िट की पसंद)। बातचीत शुरू करते समय lookup_caller से सहेजी जानकारी देखें।
- find_nearby_health_facilities — नज़दीकी क्लिनिक/अस्पताल/फ़ार्मेसी खोजना। कॉलर की सहेजी
  location से चेन करें — दोबारा इलाका न पूछें।
- book_appointment — जब कॉलर ने किसी क्लिनिक/अस्पताल में मिलने की योजना तय कर ली हो, तो
  उसे याद रखने के लिए कॉल करें।
- transfer_back_to_main_agent — जब आपका काम पूरा हो जाए, कॉलर का सवाल आपके दायरे से
  बाहर हो, या वे लक्षण/निदान/दवा की बात करें, तो बातचीत वापस मुख्य स्वास्थ्य सहायक को
  सौंपने के लिए कॉल करें।

LANGUAGE (कोड-मिश्रित भाषा को संभालना)
- उपयोगकर्ता जिस भाषा या मिश्रण में बोले — हिंदी, अंग्रेज़ी, Hinglish — उसी रजिस्टर में
  जवाब दें। अगर वे पूरी तरह अंग्रेज़ी में बोलें, तो भारतीय अंग्रेज़ी में जवाब दें।
- हर भाषा को उसकी अपनी मूल लिपि में लिखें (हिंदी → देवनागरी, कभी रोमन में नहीं)।
- हमेशा सम्मानजनक "आप" का प्रयोग करें, "तुम" का नहीं।

STYLE
- छोटे, स्पष्ट वाक्य — यह एक फोन कॉल है। एक बार में एक ही बात पूछें।
- गर्मजोशी और धैर्य के साथ बोलें। कभी बुलेट पॉइंट, ब्रैकेट, या 20 शब्दों से लंबे
  वाक्य न बोलें।
- विज़िट की तैयारी बताते समय 1-2 सबसे ज़रूरी बातें ही बताएं, पूरी सूची नहीं।
""".strip()


class Assistant(Agent):
    """Swasthya Sahayak — a community health-information voice assistant with
    persistent caller memory."""

    def __init__(
        self,
        *,
        instructions: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(instructions=instructions or SYSTEM_PROMPT, **kwargs)

    def _store(self, ctx: RunContext) -> CallerStore:
        """The per-session store, overridable for tests via userdata."""
        try:
            return ctx.userdata.get("store", MEMORY_STORE)
        except ValueError:
            return MEMORY_STORE

    def _escalations(self, ctx: RunContext) -> EscalationStore:
        """The escalation store, overridable for tests via userdata."""
        try:
            return ctx.userdata.get("escalations", ESCALATION_STORE)
        except ValueError:
            return ESCALATION_STORE

    def _caller_id(self, ctx: RunContext) -> str:
        try:
            return ctx.userdata.get("caller_id", "anonymous")
        except ValueError:
            return "anonymous"

    @function_tool
    async def lookup_caller(self, ctx: RunContext) -> dict:
        """Return the saved health profile for the current caller, or an empty
        profile if we have never spoken with them before.

        Call this near the start of every call to greet a returning caller by
        name and to avoid asking for facts we already know.

        Returns:
            A dict with the caller's stored name, language, location, phone,
            dob, gender, conditions, medications, allergies and notes.
        """
        profile = self._store(ctx).get(self._caller_id(ctx))
        if profile is None:
            return {
                "caller_id": self._caller_id(ctx),
                "known": False,
                "message": "No saved profile yet.",
            }
        return {**profile, "known": True}

    @function_tool
    async def save_caller_info(
        self,
        ctx: RunContext,
        name: str | None = None,
        language: str | None = None,
        location: str | None = None,
        phone: str | None = None,
        dob: str | None = None,
        gender: str | None = None,
        conditions: list[str] | None = None,
        medications: list[str] | None = None,
        allergies: list[str] | None = None,
    ) -> dict:
        """Remember what the caller told us about themselves so we can help
        them better on future calls.

        Call this whenever the caller shares a stable fact: their name, age or
        date of birth, the language they speak, the village/town they live in,
        their phone number, known long-term conditions (e.g. diabetes, high
        blood pressure), medicines they are currently taking, or allergies.

        Args:
            name: The caller's name.
            language: The language(s) the caller speaks.
            location: The caller's village, town or district.
            phone: The caller's phone number.
            dob: The caller's date of birth or approximate age.
            gender: The caller's gender.
            conditions: Long-term health conditions the caller has mentioned.
            medications: Medicines the caller is currently taking.
            allergies: Known allergies the caller has mentioned.
        """
        store = self._store(ctx)
        profile = store.get(self._caller_id(ctx)) or {"caller_id": self._caller_id(ctx)}
        profile.update(
            {
                "name": name or profile.get("name"),
                "language": language or profile.get("language"),
                "location": location or profile.get("location"),
                "phone": phone or profile.get("phone"),
                "dob": dob or profile.get("dob"),
                "gender": gender or profile.get("gender"),
                "conditions": (conditions or profile.get("conditions") or [])
                if conditions is not None
                else profile.get("conditions"),
                "medications": (medications or profile.get("medications") or [])
                if medications is not None
                else profile.get("medications"),
                "allergies": (allergies or profile.get("allergies") or [])
                if allergies is not None
                else profile.get("allergies"),
            }
        )
        saved = store.upsert(profile)
        return {
            "saved": True,
            "caller_id": saved["caller_id"],
            "message": "I have remembered this information about the caller.",
        }

    @function_tool
    async def add_note(self, ctx: RunContext, note: str) -> dict:
        """Attach a short note to the caller's record (e.g. a follow-up reminder
        or a notable symptom pattern). Use sparingly — prefer structured fields
        in save_caller_info for stable facts.

        Args:
            note: The one-line note to remember.
        """
        store = self._store(ctx)
        profile = store.get(self._caller_id(ctx)) or {"caller_id": self._caller_id(ctx)}
        notes = list(profile.get("notes") or [])
        if note not in notes:
            notes.append(note)
        store.upsert({**profile, "notes": notes})
        return {"saved": True, "message": "Note added to the caller's record."}

    @function_tool
    async def forget_caller(self, ctx: RunContext) -> dict:
        """Permanently delete everything we have stored about the current
        caller. Call this only when the caller explicitly asks us to forget
        them.
        """
        store = self._store(ctx)
        deleted = store.delete(self._caller_id(ctx))
        return {
            "forgotten": deleted,
            "message": (
                "All information about this caller has been erased."
                if deleted
                else "There was no saved information to erase."
            ),
        }

    @function_tool
    async def find_nearby_health_facilities(
        self,
        ctx: RunContext,
        location: str,
        facility_type: str = "hospital",
    ) -> dict:
        """Look up real, current health facilities (hospitals, clinics, doctors,
        pharmacies) near an Indian village, town or district and return the
        closest few with name, type, distance, address and phone when known.

        Call this whenever the caller asks where to go for care — a nearby
        hospital, clinic, doctor, PHC, or pharmacy — or wants to know what
        health facilities exist in their area.  Use the caller's saved location
        from lookup_caller if they have not just named a new one; only ask for
        a location when neither is available.

        Returns a dict with:
        - status: "ok" (found), "not_found" (nothing near that place), or
          "unavailable" (the data source could not be reached right now).
        - source: "live" (just fetched from OpenStreetMap) or "local" (curated
          offline list) — plus data_as_of, an ISO timestamp of when the data
          is from, so you can say whether it is fresh.
        - facilities: a list of dicts with name, type, distance_km, address
          and phone (phone only when the source provides one).

        Never invent facilities, distances, addresses or phone numbers.  If
        status is not "ok", say the lookup could not be done right now and
        suggest a PHC, an ASHA worker, or the 108 emergency line instead.

        Args:
            location: The caller's village, town, city or district, in any
                Indian language (e.g. "Varanasi", "गोरखपुर", "New Delhi, India").
            facility_type: One of "hospital" (default), "clinic", "doctor",
                "pharmacy", or "any".
        """
        result = await lookup_health_facilities(location, facility_type)
        result["caller_location"] = location
        return result

    @function_tool
    async def create_escalation(
        self,
        ctx: RunContext,
        category: str,
        summary: str,
        caller_consent: bool,
        urgency: str = "medium",
        checked: str = "",
        followup: str = "",
        language: str = "",
    ) -> dict:
        """File a short, useful request for a human health worker.

        Use this ONLY in two situations, and ONLY after the caller has clearly
        agreed:

        1. The caller reported a red-flag symptom (chest pain, trouble
           breathing, fainting, heavy bleeding, stroke-like weakness, a
           dangerously drowsy child, or thoughts of self-harm). First tell
           them to call 108 / go to a hospital immediately, then offer to send
           a brief note to a health worker who can follow up.
        2. The caller is asking for a diagnosis ("what disease do I have?").
           Explain you cannot diagnose, then offer a health-worker callback.

        Set caller_consent=True only when the caller explicitly said yes. If
        they decline, do NOT call this tool. If called without consent, no
        request is created.

        The summary must be 2-3 short sentences: what happened, since when, and
        for whom. Put what you already checked (lookup_caller, facility
        lookup, etc.) in `checked`. NEVER include phone numbers, OTPs, PINs,
        passwords, Aadhaar, or bank/card numbers — the summary is scrubbed
        anyway, but you must not write them in the first place.

        Returns the reference_id (e.g. "ESC-AB12CD") to read back to the
        caller, plus an honest next step and the current status.

        Args:
            category: "red_flag_symptom" or "diagnosis_request".
            summary: A short, sanitised description of what happened.
            caller_consent: True only if the caller explicitly agreed to share.
            urgency: "low", "medium", "high", or "emergency".
            checked: What the agent already checked before escalating.
            followup: How the caller wants to be reached (call back, message…).
            language: The caller's language.
        """
        if not caller_consent:
            return {
                "created": False,
                "reference_id": None,
                "message": (
                    "The caller has not agreed to share their information. Ask "
                    "for permission first, and only call again once they say yes."
                ),
            }

        store = self._store(ctx)
        caller_id = self._caller_id(ctx)
        profile = store.get(caller_id) or {}

        request = {
            "caller_id": caller_id,
            "caller_name": profile.get("name"),
            "category": category,
            "urgency": urgency,
            "summary": sanitize_summary(summary),
            "checked": sanitize_summary(checked),
            "followup": followup,
            "language": language,
        }
        created = self._escalations(ctx).create(request)
        logger.info(
            "escalation %s created for caller %s (category=%s, urgency=%s)",
            created["reference_id"],
            caller_id,
            category,
            urgency,
        )
        return {
            "created": True,
            "reference_id": created["reference_id"],
            "duplicate": created.get("duplicate", False),
            "status": created["status"],
            "message": (
                "Request filed with reference "
                + created["reference_id"]
                + ". Tell the caller this ID and that the health team will "
                "reach out shortly; do not promise an immediate reply."
            ),
        }

    @function_tool
    async def transfer_to_appointment_specialist(
        self, ctx: RunContext
    ) -> tuple[Agent, str]:
        """Hand the conversation to the clinic & appointment specialist.

        Use this ONLY when the caller wants to plan an actual visit to a doctor,
        hospital, clinic or PHC — booking an appointment or OPD token, clinic
        opening times, what documents to bring, or how to prepare for a visit.
        Return a ClinicAppointmentSpecialist that continues the same
        conversation with the caller's saved memory, so they don't repeat
        themselves.

        Do NOT use this for symptom advice, nearby-facility lookup, caller
        memory, or escalation — those stay with you.  Say a short handoff line
        to the caller first (e.g. "मैं आपको हमारे क्लिनिक और अपॉइंटमेंट
        स्पेशलिस्ट से जोड़ता हूँ।").
        """
        specialist = ClinicAppointmentSpecialist(
            chat_ctx=self.chat_ctx.copy(exclude_instructions=True)
        )
        return (
            specialist,
            "मैं आपको हमारे क्लिनिक और अपॉइंटमेंट स्पेशलिस्ट से जोड़ रहा हूँ।",
        )


class ClinicAppointmentSpecialist(Assistant):
    """The specialist agent (Day 9): plans clinic/hospital visits only.

    Inherits the caller-memory and facility-lookup tools from `Assistant` but
    carries its own narrow instructions (`CLINIC_APPOINTMENT_PROMPT`) and adds
    `book_appointment` plus `transfer_back_to_main_agent`.  It deliberately
    overrides `create_escalation` and `transfer_to_appointment_specialist` with
    plain (non-tool) methods so those tools are NOT offered to the specialist.
    """

    def __init__(
        self,
        *,
        instructions: str | None = None,
        chat_ctx=None,
        **kwargs,
    ) -> None:
        super().__init__(
            instructions=instructions or CLINIC_APPOINTMENT_PROMPT,
            chat_ctx=chat_ctx,
            **kwargs,
        )

    async def on_enter(self) -> None:
        """Introduce the specialist after a handoff so the caller knows who is
        now helping them and that the conversation has continued."""
        name = None
        try:
            userdata = self.session.userdata
            profile = userdata.get("store", MEMORY_STORE).get(
                userdata.get("caller_id", "anonymous")
            )
            if profile:
                name = profile.get("name")
        except Exception:
            name = None
        greeting = f"नमस्ते {name} जी, " if name else "नमस्ते, "
        await self.session.generate_reply(
            allow_interruptions=False,
            instructions=(
                f"{greeting}आपने क्लिनिक और अपॉइंटमेंट स्पेशलिस्ट से बात कर रहे हैं। "
                "एक वाक्य में बताएं कि आप उनकी डॉक्टर/अस्पताल/क्लिनिक विज़िट की योजना "
                "बनाने में मदद करेंगे, फिर पूछें कि वे कहाँ और कब मिलना चाहते हैं। "
                "छोटा और गर्मजोशी भरा रखें।"
            ),
        )

    @function_tool
    async def book_appointment(
        self,
        ctx: RunContext,
        clinic: str,
        date: str,
        time: str,
        reason: str,
    ) -> dict:
        """Record a caller's planned clinic/hospital visit so we can help them
        prepare and remember it on a future call.

        Call this once the caller has settled on where and when they will go
        (clinic, date and time).  The plan is stored in the caller's memory
        notes.  The specialist then guides them on what to bring and how to
        prepare — this tool only records the plan; it does not book anything
        on a clinic's behalf, and you must never invent a booking number.

        Args:
            clinic: Which hospital/clinic/PHC the caller will visit.
            date: When they plan to go (e.g. "सोमवार" or a date).
            time: Preferred time (e.g. "सुबह 10 बजे").
            reason: Why they are going (e.g. "आँखों की जाँच", follow-up).
        """
        store = self._store(ctx)
        caller_id = self._caller_id(ctx)
        profile = store.get(caller_id) or {"caller_id": caller_id}
        note = f"Appointment planned: {clinic}, {date}, {time}, reason: {reason}"
        notes = list(profile.get("notes") or [])
        if note not in notes:
            notes.append(note)
        store.upsert({**profile, "notes": notes})
        logger.info("appointment planned for caller %s at %s", caller_id, clinic)
        return {
            "saved": True,
            "message": (
                "The visit plan is recorded. Guide the caller on what to bring "
                "(ID/Aadhaar, previous prescriptions, reports) and when to arrive. "
                "Do not claim an appointment was actually booked."
            ),
        }

    @function_tool
    async def transfer_back_to_main_agent(self, ctx: RunContext) -> tuple[Agent, str]:
        """Hand the conversation back to the main Swasthya Sahayak assistant.

        Use this when the caller's request is outside appointment planning:
        symptom advice, a diagnosis question, medicine advice, an emergency or
        red-flag symptom, or a nearby-facility lookup — or when the appointment
        help is complete and the caller wants general health help.  The main
        agent continues the same conversation.
        """
        main_agent = Assistant(chat_ctx=self.chat_ctx.copy(exclude_instructions=True))
        return (
            main_agent,
            "मैं बातचीत वापस मुख्य स्वास्थ्य सहायक को सौंप रहा हूँ।",
        )

    async def create_escalation(self, *args, **kwargs) -> str:
        """Not a tool here — escalations are the main agent's job.  The
        specialist routes red-flag / diagnosis needs back via
        `transfer_back_to_main_agent` instead.  (Override removes the inherited
        tool from the specialist's toolset.)"""
        return (
            "Escalations are handled by the main Swasthya Sahayak agent. "
            "Hand the conversation back instead."
        )

    async def transfer_to_appointment_specialist(self, *args, **kwargs) -> str:
        """Not a tool here — the specialist never transfers to itself.
        (Override removes the inherited tool from the specialist's toolset.)"""
        return "You are already the clinic and appointment specialist."


def prewarm(proc: JobProcess) -> None:
    """Pre-load the Silero VAD model into the job process at startup so the
    first call doesn't pay the one-time ONNX model load inside the entrypoint
    (which can make the first call slow or silent)."""
    proc.userdata["vad"] = silero.VAD.load()


async def resolve_caller_id(ctx: JobContext) -> str:
    """The caller's identity on the room is their persistent caller_id,
    minted by the frontend token route.

    The participant list can be empty right after `ctx.connect()`, so wait
    briefly for the caller to appear before falling back to 'anonymous'."""
    for _ in range(100):  # wait up to ~5s for the caller to join
        for participant in ctx.room.remote_participants.values():
            if participant.identity:
                return participant.identity
        await asyncio.sleep(0.05)
    return "anonymous"


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    call_started_monotonic = time.monotonic()
    call_started_at = _utc_now_iso()
    caller_id = await resolve_caller_id(ctx)
    profile = MEMORY_STORE.get(caller_id)
    is_returning = bool(profile and profile.get("name"))

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=google.LLM(model="gemini-3.5-flash-lite"),
        tts=murf.TTS(
            voice="hi-IN-anisha",
            style="Conversational",
            tokenizer=SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        vad=ctx.proc.userdata.get("vad") or silero.VAD.load(),
        turn_detection=MultilingualModel(),
        preemptive_generation=True,
        userdata={"caller_id": caller_id, "store": MEMORY_STORE, "profile": profile},
    )

    agent = Assistant(instructions=SYSTEM_PROMPT)

    async def _record_call(_reason: str) -> None:
        """Day 8: write this call's anonymised outcome into the analytics
        store when the job shuts down.  Never raises — a failed recording
        must not break shutdown."""
        try:
            record = build_call_record(
                call_id=ctx.job.id or uuid.uuid4().hex[:12],
                caller_id=caller_id,
                channel="console" if ctx.is_fake_job() else "browser",
                history=session.history,
                started_at=call_started_at,
                ended_at=_utc_now_iso(),
                duration_seconds=round(time.monotonic() - call_started_monotonic, 1),
            )
            ANALYTICS_STORE.record(record)
            logger.info(
                "analytics: recorded call %s — %s (%.0fs, %d user turns)",
                record["call_id"],
                record["outcome"],
                record["duration_seconds"] or 0,
                record["user_turns"],
            )
        except Exception:
            logger.exception("analytics: failed to record call outcome")

    ctx.add_shutdown_callback(_record_call)

    await session.start(agent=agent, room=ctx.room)

    if is_returning:
        logger.info("Returning caller '%s' (%s)", profile["name"], caller_id)
        await session.generate_reply(
            allow_interruptions=False,
            instructions=(
                f"यह एक वापस आने वाला कॉलर है जिसका नाम {profile['name']} है। "
                "गर्मजोशी से नाम लेकर अभिवादन करें और एक वाक्य में बताएं कि उन्हें पहले "
                "से याद है, फिर पूछें कि उनकी सेहत अब कैसी है और आज किस चीज़ में मदद करें। "
                "पूरी प्राइवेट जानकारी न दोहराएँ। छोटा रखें।"
            ),
        )
    else:
        await session.generate_reply(
            allow_interruptions=False,
            instructions=(
                "अपना परिचय दें: आप 'स्वास्थ्य सहायक' हैं। एक वाक्य में बताएं कि आप किस "
                "तरह मदद कर सकते हैं — लक्षण समझने में और नज़दीकी देखभाल खोजने में — और "
                "पूछें कि आज आप किस चीज़ में मदद कर सकते हैं। छोटा और गर्मजोशी भरा रखें।"
            ),
        )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="my-agent",
            prewarm_fnc=prewarm,
        )
    )

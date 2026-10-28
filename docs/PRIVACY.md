# What leaves your computer

Kurooto runs on your computer, and every feature is off until you turn it on. This page lists, per feature, exactly
what goes where. **Nothing is ever sent to Kurooto's author** (no analytics, no crash reports, no "phone home"). The
only things Kurooto fetches from its own release page are updates and the list of withdrawn versions, both checked
against a signature.

Everything below goes to services you chose, under your own accounts.

The screenshots in the README and on the website are of a demo with made-up data ("Sam") and stand-in services; none
of them shows anyone's real notes, chats or accounts. The pages' colours (`look.palette`) are a setting on this
computer only.

## Always (when the feature is on)

| Feature | What leaves | Where to |
|---|---|---|
| Telegram | your messages to the bot and its replies; files you send it | Telegram (to your own bot) |
| Questions and approvals | the question or approval, wherever Kurooto reaches you; open ones are also in the brief your call line keeps (see Phone calls) | Telegram (your own bot) and your paired phones; desktop notifications stay on this computer |
| Chat with your AI | what you ask; notes the AI reads to answer; what its tools return (a note's text, your reminders or deadlines); the short "In brief" part of your profile, your how-to-help-me note and your persona card (empty unless you write one) | the AI service you picked (Google for agy/Gemini, Anthropic for Claude Code, the service you entered for a custom one, or nothing for local models) |
| Help with your project (off; per project `/project help on`) | your request and the files of that project the AI reads or changes in its scratch folder (`<state>/scratch/`, on this computer); nothing is pushed, sent or published. Checks you set for a project run with no network, in a sandbox | the AI service you picked |
| Proposals (0.7.0) | nothing new: a change to your notes you asked for goes to the AI as before; the AI now writes it in a scratch folder on this computer and you apply it. Keys and passwords (`.env`, `*.pem`, `id_rsa` ...) are never copied there or proposed | the AI service you picked |
| Notes sorter (0.7.4, off until you turn it on) | only for a note its rules can't place, with `sorter.ai` on: the note's first lines (about 1,500 characters) and the names of your folders, as one short request; rules-only (`sorter.ai` off) sends nothing. Its state (`state/sorter/state.json`: where it moved notes, what it learned from your moves, what waits) stays on this computer | the AI service you picked |
| Files into notes | with Chat on, the files you send, for the AI to file them | the AI service you picked |
| Photo to dates | the photo you sent for its dates (`dates` as its caption, `/dates`, "dates from that photo"); agent programs open it where it was saved, API brains get it with the request. What it found stays here, offered with Add buttons; nothing is added before a tap | the AI service you picked |
| Setup page: Try it now | what you type in the box that isn't an instant request (a reminder, a command), like a Chat message; nothing goes to Telegram or your phone | the AI service you picked |
| Skills | what you send with a skill and the notes it reads; for `/newskill`, your description and the names of your tools and skills | the AI service you picked |
| Hint ladder | the problem (its photo or text), the course's AI-policy line and the notes the AI reads to find the lecture note; with "no AI help" in that line, nothing | the AI service you picked |
| Skills: revision packs | Tectonic (if you install it) downloads LaTeX packages; nothing of yours is sent | Tectonic's package server (public) |
| Research add-on: LaTeX tracker | Tectonic (if it's installed) downloads LaTeX packages it lacks; nothing of yours is sent. A BibTeX suggestion, only when you tap for one: the citation key and the sentence it's cited in | Tectonic's package server (public); the AI you picked |
| Check my draft (Research add-on) | the draft you send (a photo, PDF, `.tex`, essay or code, a text file numbered line by line) and the course notes the AI reads; with the course's AI policy `off`, nothing | the AI service you picked |
| Course notes to PDF (`/notes pdf`) | nothing: your notes become LaTeX and a PDF on this computer; Tectonic may download LaTeX packages it lacks | Tectonic's package server (public), only for packages |
| Study packs (`/studypack`) | nothing to your AI: Kurooto collects the files on this computer and fills in a prompt. With a topic, it finds each book's pages on it in the text Books extracted, on this computer. The zip and the prompt come to your own Telegram; you decide which other AI to give them to | Telegram (your own bot); with Drive upload on, a pack over 50 MB goes to your own Drive, deleted after `drive_upload.temp_days` |
| Skills: packs before exams (`skills.auto_pack`) | the same as `/pack`: the subject's notes the AI reads to write the pack; with `ask` (the default) only after you tap Build it | the AI service you picked |
| Sending files (`kurooto send`, the AI's send-file tool) | the file | Telegram (to your own bot) |
| Class packs | a pack you make: the section's courses, timetable, term dates, quizzes and exams, never names, keys, notes or skills; you decide whom to forward it to. Importing one sends nothing | Telegram (to your own bot) |
| Check-ins | nothing; with Check-ins by call and Chat on: what you said on the check-in call (after the evening debrief, both sides of it), for the AI to write your journal and study logs | the AI service you picked |
| Quiz | nothing; with Chat on: the question from your notes and your answer, for the AI to grade | the AI service you picked |
| Weekly summary | nothing; with the Sunday review call and Chat on: the call's transcript, to write the weekly review | the AI service you picked |
| After-class notes | nothing; with Chat on: your answer and the photos and files you sent with it, for the AI to write a study log | the AI service you picked |
| Brain's read, forecast and tone tag (0.8.0, `mind.read.on`, `mind.forecast.on`, `mind.tone.on`; the tone tag is off by default) | nothing: numbers about your days, the read and the forecast stay in the `mind` folder (30 days; your answers 7), the tone tag uses the model on this computer only | stays on your computer |
| Brain's body budget, values, feelings and promises (0.8.0, `mind.budget.on`, `mind.values.on`, `mind.feelings.on`, `mind.promises.on`, `mind.heartbeat.on`) | nothing: numbers about Kurooto's own state in the `mind` folder; its promises (a sentence and a time, 30 days) and its current feeling in the state folder. An AI request carries the rule about feelings and, rarely, a hint like "keep it short", never a reading of you | stays on your computer |
| Brain's journal (0.8.0, `mind.journal.on`, `mind.journal.in_notes` off) | nothing: a short file a day in the state folder, worded on this computer and checked against Brain's log | stays on your computer |
| Brain's life story (0.8.0, `mind.story.on`) | the summary (its fixed core and a few of its own checked journal lines) goes in front of each AI request and call, to the AI you chose; nothing of how you're doing | the AI you chose, with the request |
| Brain's hidden harness (0.8.0, `mind.harness.on`) | nothing: made-up tasks, nightly, with Kurooto's own rules answering; the scores stay in the `mind` folder | stays on your computer |
| Brain's workspace and beliefs (0.8.0, `mind.workspace.on`, `mind.beliefs.on`) | nothing about how you're doing; "On my mind right now: ..." lists the winning deadlines, promises and goals (their titles) in front of each AI request | the AI you chose; the rest stays on your computer |
| Brain's precedents and play (0.8.0, `mind.precedents.on`, `mind.play.on`, both off) | nothing leaves: your rulings stay in `mind-precedents.json`; a play question's text goes to the AI you chose (a concept from your notes, no personal details) | the AI you chose, for play questions only |
| Brain's forgetting (0.8.0, `mind.forget.on`) | nothing: it only removes; `mind-forget.json` keeps how often a memory was used (no words); a forget leaves a hash and a count in Brain's log | stays on your computer |
| Brain's plans (0.8.0, `mind.plans.on`) | nothing: simulated on this computer from your deadlines, pace and calendar | stays on your computer |
| Brain's model of your mind (0.8.0, `mind.tom.on`) | nothing, except one line to an AI request saying how well you know the concepts it names ("new to them: define it first"); the rows stay in `mind-tom.json`; no health, relationships, politics, religion or money | the AI you chose, only the pitch line |
| Brain's senses (0.8.0): its own machine (`mind.senses.intero`, on); your activity (`mind.senses.activity`, off); each phone sensor (`mind.senses.phone.<sensor>`, off) | nothing: readings stay in the `mind-senses` folder (raw 7 days, then totals); phone readings are sealed on the phone with its key and pass through your call line, which can't read them; never the microphone, keystrokes, screen, URLs or per-app time | stays on your computer |
| Brain's feelings, mood, talk reward, not-a-pest model and body map (0.8.8, `mind.feelings.mood`, `mind.feelings.empathy`, `mind.feelings.vocal` off, `mind.talk.on`, `mind.pest.on`, `mind.stimulation.on`) | nothing about how you're doing: the talk reward's facts (that a message came, whether you were in focus, asleep or in an exam window; never its words) and the mood stay in the `mind` folder; the welcome counts (no words) in `mind-pest.json`; the body map (numbers only, latest reading) in `mind-stimulation.json`, and the dashboard reads it from this computer (`/api/body`). An AI request may carry its own mood ("keep your messages short") and the names of things at risk it should mention gently (a deadline's title, a project, "your supervisor"), never a reading of you | the AI you chose, only those two lines; the rest stays on your computer |
| Brain's skills and fine-tune (0.8.0, `mind.skills.on`, `mind.finetune.on` off) | a skill is made by the AI you chose from a task's request and summary (never health, money or chats); the fine-tune stays on your computer: the training text is deleted after each run, and forgotten items leave a hash and a few words | the AI you chose, for making a skill |
| Brain's lab and self-improvement (0.8.0, `mind.lab.on`, `mind.improve.on`) | nothing: your project's code runs on your computer in a sandbox with no network; with a free-form code search your AI sees the project's top Python files to propose changes (the AI you chose); results stay in the state folder | the AI you chose, only for free-form proposals; the rest stays on your computer |
| Notes brain (GBrain) | nothing on computers with a graphics card or Apple Silicon (the index is made locally); on others, note text, to make the index. The nightly upkeep and timelines add nothing: the upkeep's index step sends note text to Google only if your index already uses Gemini. Kurooto turns off GBrain's own update check, so GBrain makes no calls to its release page | Google (Gemini, your key), unless you chose keyword-only |
| Notes brain: your own GBrain (`gbrain.managed` = `false`) | nothing by Kurooto: it runs your gbrain program, which uses the embedding and AI models *your* brain is set up with (also for the upkeep steps you add, such as contradictions). With `gbrain.agy_mcp` and your approval, agy can use your brain's tools, so what it reads there goes to Google like the rest of agy's work | whatever your own brain is set up to use; Google (agy) with `gbrain.agy_mcp` |
| Memory: what an AI reply is told | only when your message refers to past things ("on the call", "yesterday", "that thing", "did I ...", a weekday) or shares words with an open thread: at most about 600 tokens (`memory.budget_tokens`) of one-line items from the memory ledger (open threads, gists, meeting and daily-note lines), each saying where it's from, never transcripts, with that request. A call's brief also gets your open threads and the last day's gists. `memory.recall` = `false` sends none | the AI service you picked; for calls, Google (Gemini Live, your key) |
| What Kurooto is running (`self.md`, 0.6.0) | only with a request about Kurooto itself ("why didn't it ring?", "which model answered?"), when the AI calls `kurooto_self`, and with `/fixme`'s Ask my AI: Kurooto's version and update channel; the OS, processor, memory, graphics and hardware profile; the AIs set up with their models, fallback order, limits and today's counts; each feature's id, on or off and its health check's line; the last day's failures counted by kind (an event's kind, the AI, verdict, feature and an error's kind: never its text); the last few requests' status, AI, model, effort and time (never their titles or words); the paths of the settings, log and notes folders. Never messages, notes, request titles, answers or secrets | the AI service you picked |
| Remember | your how-to-help-me note (`about-me/how-to-help-me.md`) goes along with every AI request, like the profile's "In brief" part; health, money and password details are refused, never stored. "Still true?" (`remember.recheck_days`, 90) is worked out on this computer: when each line Kurooto wrote last came up, kept by a hash of its words in the state folder | the AI service you picked |
| Nightly look back | what happened (events: what you answered, moved, skipped, and when), Kurooto's questions and your answers, today's call transcripts and journal (each can be left out), your how-to-help-me note and the values of the settings it may change; for a skill change you approved, that skill's text | the AI service you picked |
| Learns from its own work (optional) | its search index of past requests, calls and chats is built and kept on this computer; when the AI searches it, the passages it finds go to that AI with the request; to learn a skill, the finished request, its answer and the steps it took; to learn a lesson, your correction and the skill; with the nightly look back, the day's requests, to pick out facts you stated (never health, money, passwords or other people's details) | the AI that takes second looks (`learning.brain`), else the AI service you picked |
| Phone calls | call audio and what's said on calls; the call setup (your name, the assistant's name, which tools exist); for calls while the computer is off: a short brief (what's due, today's classes and check-ins, open questions, quiz questions, the alarm), the steps for check-in, wake-up and Sunday review calls with what they need (today's plan from your daily note, today's classes, study hours counted, the week's numbers), and your notes' titles, headings and first lines | Google (Gemini Live, your key); your own Cloudflare account (your call line) |
| Phone calls: the look back after every call (`calls.review`, on; off stops it) | the call's transcript and its tool log (each tool it used, with what it was given and returned), for an AI request that does what slipped through and writes lessons for later calls; the lessons then go with every call's setup | the AI service you picked (or `calls.review_brain`); the lessons to your call line and Google (Gemini Live), like the rest of the call setup |
| Phone calls: transcripts while the computer is off | the call's transcript, held by your call line until your computer is back (at most the last 200 waiting items), then passed to it | your own Cloudflare account (your call line) |
| Phone calls: turn by turn (`calls.voice_mode` `phone`, or when Gemini Live is down) | your speech, to your phone's speech recognizer: on Android 13+ with your language downloaded it's recognised on the phone and stays there; otherwise your phone's speech service (usually Google's; Apple's on iPhone; Chrome sends it to Google). The text of each turn, the call's instructions and its tools' answers | the speech service your phone uses; Google (Gemini, your key) from your computer or your call line, or the model on your computer (`calls.turn_brain` = `local`): never an agent program |
| Phone calls: text on Telegram (no speech recognition or microphone) | the call's conversation, as messages | Telegram (your own bot) and the AI service you picked, like your other messages |
| Phone calls: how Live failed | which Live model failed, Google's error code, and what the call did instead, counted for `kurooto doctor` | your call line passes it to your computer; it stays there |
| Phone calls: ringing and messages | "a call is ringing" messages, and the questions, approvals and messages you choose for the phone (`notify.app_kinds`), encrypted with a key only your paired Android phones, your computer and your call line hold (ntfy can't read them) | your own Cloudflare account (your call line: since 0.7.0 the Android app gets them on its own connection to it, and the line keeps the last 60, sealed, for 6 hours for a phone that reconnects); ntfy.sh only as the Android fallback and a second copy of each ring (with `kurooto ntfy-token`, as your ntfy account: the token is kept on this computer and your call line); Apple/Google push services (web app; the push itself is empty) |
| Phone calls: what's waiting | the text of open questions, approvals and messages sent to your phones (at most 40; a message is gone after a day, a question or approval once it's answered or expires), so the iPhone app can list them | your own Cloudflare account (your call line) |
| Phone calls: the app's chat | what you type in the phone app's chat and Kurooto's answers (with `notify.app_chat` on, or without Telegram, its other messages too). Your call line keeps the chat's last 50 messages, each for at most 3 days, so a phone can catch up while this computer is off; Kurooto's messages go to Android phones encrypted as above. With separate chats (0.8.10, `calls.chat_sessions`) it keeps the last 50 of each chat, and the list of chats (each one's name: its first words or, with `calls.chat_titles` = `ai`, a title your AI wrote from the first message and answer; its last line and times) and the list of commands (Telegram's menu, your skills' names included) until the chat is deleted; "working"/"idle" goes only to phones connected to the line and isn't kept | your own Cloudflare account (your call line); ntfy.sh (Android, encrypted) or Apple/Google push (web app; the push itself is empty) |
| Phone calls: files for the app's chat (without Telegram) | where Telegram would get a document (a long answer, a file you or your AI send yourself): with Drive upload on, the file goes to your own Drive (see Drive upload); otherwise a copy encrypted on this computer with a fresh key (AES-256-GCM), kept on your call line for a day (at most 10 MB each, 30 MB in all) and then deleted. The key is only in the link, which travels inside the chat message, so the copy is as private as the chat itself; the file page opens it in your phone's browser | your own Cloudflare account (your call line); Google (your Drive) with Drive upload on |
| Phone calls: files you shared, for the chat's AI | the names and paths of files you shared from the phone in the last two hours, told to your AI with a request that talks of a file ("summarise the PDF I just sent"); a file sent into one of the app's chats (0.8.10), with every request in that chat that talks of a file, however long ago; the list stays on this computer | the AI service you picked |
| Phone calls: the being on the Android app (0.8.10) | a setting changed or a feature turned on or off from the app's Views tab, and the text of a note you open there (as the dashboard shows it, at most 4000 characters): sealed by the app, passed by your call line only while this computer is on (never kept), applied here with the dashboard's own checks, and the answer sealed for that phone alone (your call line can't read it) | your own Cloudflare account (your call line), sealed |
| Phone calls: Tell Kurooto (the iPhone Shortcut, 0.6.0) | what you say to the Shortcut, as text (dictated on the iPhone), passed on like a chat message from that iPhone; for each link, a hash of it (never the link itself), the phone it belongs to, and when it was made and last used. The link can only send chat messages; revoke it on the dashboard (Phone) | Apple (the iPhone's dictation); your own Cloudflare account (your call line), then this computer |
| Phone calls: bedside mode (Android, 0.6.0) | nothing new: the phone reads from your call line the calls already booked there (times and reasons) and how many things wait for you | your own Cloudflare account (your call line), already |
| Phone calls: the phone outbox | chat messages, button taps, answers and shared files (at most 100 things and 20 MB of files) sent from a paired phone while this computer is off, held until it's back and takes them, then deleted; for a day after, the ids of what went through and this computer's short note on each, so the phone can show it | your own Cloudflare account (your call line) |
| Going offline and coming back (on by default) | the "going offline", "back online" and "network was down" messages, and messages kept while the network was down | Telegram (your own bot); with Phone calls, the phone app through your call line |
| Going offline + Phone calls | your night and focus hours for the next day and the message's wording, so your call line can say "offline since 22:10" while this computer can't; only after you approve (asked once): your Telegram bot's token and your chat id, kept in your call line's storage and deleted there when you set `notify.presence.line_telegram` to `false` or turn the feature off | your own Cloudflare account (your call line), which then sends to Telegram or your phones |
| Morning alarm | the alarm time; with Chat on, the AI reads your notes before the alarm to draft the day's plan, and the wake-up call's transcript to settle it | your call line; the AI service you picked |
| Exam season | nothing; with Phone calls on, the leave-by alarm (its time, the exam and what you said about the venue), so your call line can ring it while this computer sleeps, and the exam in the brief of calls that day and the day before | your own Cloudflare account (your call line); Google (Gemini Live) on the call |
| Location reminders (`reminders.places`, off by default) | the place's name and the reminder's text, to your Android app; where your places are (saved on the phone) and when you arrive never leave the phone. Android works out where the phone is from Wi-Fi, the phone network and GPS, as for any app with location | your own Cloudflare account (your call line); ntfy.sh (encrypted, as phone messages are) |
| Reminders with the lid shut | for the next day: each reminder and a morning line (the day's first class and what's due), as a time, an id and, for each paired Android phone, a copy sealed with a key only that phone has (your call line can't read them); each phone's public key. When this computer is asleep at an item's time, its sealed copy goes out through ntfy. Your Telegram bot's token isn't used | your own Cloudflare account (your call line); ntfy.sh, still sealed |
| Systems and the Notes map on the Android app (`calls.views`, off by default; 0.7.0) | the notes map: each note's path in your notes folder, its title, when it changed, how many words it has and which notes link to which (never what a note says; a big folder is cut to `calls.views_notes` best-linked notes and `calls.views_links` links, 5000 and 20000 by default), and the research hub's project names; SYSTEMS: each feature that's on, how busy it was, its program's cpu, memory, threads and uptime, when it last did something and runs next, its health lines (as /health words them), Kurooto's own cpu and memory, the processor's load, and today's class and event times (no names). Each copy is gzipped and encrypted once on this computer with a fresh key (AES-256-GCM), and that key is sealed for each paired Android phone with a key only that phone has (as Reminders with the lid shut), so your call line keeps the newest copy of each and can't read them. The notes map goes when your notes change (at most every few minutes) and hourly; Systems only while the app shows it (it says so every 20 seconds). Turned off, the call line deletes its copies. The iPhone app gets nothing | your own Cloudflare account (your call line), sealed |
| The Brain on the Android app (`calls.views_brain`, on but only with `calls.views` and Brain on; 0.8.10) | the Brain console's copy (`mind/console.py`): Brain's decisions with their reasons and evidence (action ids, the reason codes, the AI's stated reason as kept in the log, scores), the newest 240 log records (kinds, ids and numbers: the log never holds a message's words), each Brain part's on/off state, settings and activity counts, its beliefs and the model of you (their words, source and confidence), the spotlight's items (not the ones about you), lab projects' names and results, skills' names, milestones' titles and risks, promises' words, counts of senses, forgets, stops and limits, and the journal's and life story's headings (day or week and line counts, never their sentences). Anything that names money or health is left out. Sealed as Systems is (a fresh key, sealed for each paired Android phone), sent only while the app has the Brain open, every few seconds; the call line keeps the newest copy and can't read it. Turned off, an "off" copy replaces it. The iPhone app gets nothing | your own Cloudflare account (your call line), sealed |
| The being on the Android app (`calls.views_being`, on while `calls.views` is; 0.8.10) | with each Systems copy: every feature on or off, the titles of the AI requests running and answered lately, the labels of what's scheduled next and the calls booked, this computer's readings (processor, memory, graphics, disks, battery, temperatures), Voice's state, the kinds and times of the last events (not what they say), and the settings the being's panels show with the Brain's parts and their switches (when they change). A note's text only when you tap that note on the phone, sealed for that phone. What goes to the phone is sealed as above: the call line can't read it. Changes you make there (a setting, a feature on or off, mute, which note to preview) go the other way like a chat message, sealed with the chat's key (which your call line holds too, as for chat), never kept there, and are checked as the dashboard's are | your own Cloudflare account (your call line), sealed |
| Voice notes | the recordings | Google (Gemini, your key) |
| Voice: talk and listen (0.8.8, off; listening `voice.listen.on` off too) | speaking: nothing (the voice is made on this computer by Kokoro or Piper). Listening: nothing while the portal is closed: sound is cut into stretches of speech in memory, written out on this computer (faster-whisper) and judged on this computer (Silero VAD, its name, your own openWakeWord model if you set one, rules and the model on this computer, Ollama at 127.0.0.1); noise and chatter are dropped on the spot and their words are never stored, logged or sent. Only turns the gate decides are said to Kurooto (its name, your own wake word, a follow-up in an open conversation, or the local model's judgement at `voice.listen.threshold`) go out, as text, like a chat message; they and the answers are kept in the chat history as typed ones are. Sound is never written to disk. Setting it up downloads packages from PyPI (through uv or pip) and models from github.com and huggingface.co; nothing of yours is sent. With `voice.listen.fast_brain` `fastest` (0.8.16, not the default) a plain-chat turn may go to another AI you set up (a Gemini key) instead; `local` keeps it on this computer. Turn times (`voice.listen.timing`) are numbers only and stay here | the AI you picked (addressed turns only) |
| Voice: Live at the desk (`voice.listen.live`, 0.8.17, off) | the sound of your own turns said to Kurooto, and only those: addressed by the gate (not chatter or noise), your voice by Voice ID, and a face seen close to the camera and facing it during that turn (turns let through without a face seen, such as the wake word, go the usual way). With each session, what a call's setup carries (your name, the assistant's name, which tools exist, the lessons from earlier calls) and a turn's tool results. The session lasts while the conversation is open. Nothing is written to disk; events hold numbers only | Google (Gemini Live, your key) |
| Voice ID (0.8.10, off: `voice.speaker_id.on`; improving over time `adapt` off too) | nothing. Each stretch of speech (with `voice.speaker_id.gate`, before it's written out; without it, only turns said to Kurooto) is scored against your voice print on this computer (CAM++, ONNX, on the processor) and the sound dropped; someone else's talk that isn't calling Kurooto is dropped as chatter without being written out (only its first and last two seconds are, to hear its name). Kept: only your voice print (vectors, condition names, dates, thresholds, quality numbers, the microphone's name), AES-256-GCM sealed in `state/voiceid/template.bin`, its key `biometric.voice.key` in the keychain (or the owner-only secrets file); never your recordings, never others' voices (scored in memory, then gone), never backed up, synced, in a diagnostics bundle, logged, on the live stream or shown. Words a guest says to Kurooto go to the AI like any turn but with none of your data (no notes, memory, profile, history, files or tools), or only to the model on this computer with `guest_brain: local`; they aren't kept in your history (the last four turns stay in memory for that conversation, and the request's words are blanked once the answer is spoken; only a row titled "Guest" stays in the request list). Setting it up downloads the speaker model (28 MB) from github.com (served by release-assets.githubusercontent.com) and kaldi-native-fbank from PyPI (uv or pip), or installs them from files you give; no cloud API at any step. `/voice id forget`, the Your voice page, `kurooto voice id forget` or `/forget all` delete the file and its key. Licences: CAM++ (3D-Speaker, Apache-2.0), its ONNX conversion (sherpa-onnx, Apache-2.0), kaldi-native-fbank (Apache-2.0), onnxruntime (MIT), numpy (BSD-3-Clause); the impostor set is embeddings computed from LibriSpeech (CC BY 4.0), no audio | the AI you picked (a guest's chat turns, without your data), or nothing with `guest_brain: local` |
| Face presence (0.8.10, off; nothing watches until you enrol) | nothing. The camera's frames are looked at in memory (YuNet finds faces, SFace turns yours into 128 numbers, both on this computer's processor) and dropped; the enrolment page's preview is a JPEG made in memory and drawn only on the page, never saved; someone else's face is dropped with the frame and only counted. Only your template is kept: numbers that describe your face (never a picture), sealed with AES-GCM under the key `face.key` in the keychain (else Kurooto's owner-only settings file), in `state/face/`; never in Backups, Profile sync or the diagnostics bundle (that says only on or off, enrolled, how many samples). Events say when, never a score. A face match never approves or unlocks anything. Setting it up downloads two models from media.githubusercontent.com (OpenCV's model zoo: YuNet MIT, SFace Apache-2.0) and opencv-python-headless and numpy from PyPI (through uv or pip); nothing of yours is sent | nowhere |
| Calendar | nothing leaves; Kurooto reads your calendar's private link (or Google Calendar), and class calendars you subscribed to by link (`/cal subscribe`; only fetched, nothing is sent back, and what you add from them stays here). Event descriptions are read only for `#nocall`, `#focus` and `#private` and aren't kept. Events marked private are kept and told only as "Busy (private)": their title and place go nowhere, not even to your AI | (read from Google/Outlook/Apple) |
| Notes sync | your whole notes folder; conflict copies (when a note changed here and elsewhere at once) are ordinary notes and go too | your own private GitHub repository |
| Notes sync + Phone calls | read access to that repository, so calls can read notes while the computer is off | your call line (its secret store) |
| Backups | a zip of Kurooto's settings, data and state (AI requests and answers, check-ins, deadlines, your profile reports); your notes and your keys only if you turn them on, the memory ledger only with `backups.memory` (encrypted). Not encrypted otherwise | only the folder you pick; if your computer syncs that folder to a cloud (Google Drive, OneDrive, iCloud, Dropbox), that cloud |
| Profile sync | your settings, passwords and keys, and saved state (deadlines, quiz progress, routines, observations, scheduled reminders and calls), all encrypted with your passphrase before they leave; in plain text only when it was saved, Kurooto's version, the kind of computer and a random id for it | your own private GitHub repository (the one Notes sync uses, or another you pick) |
| Google | Kurooto reads Classroom and, with Gmail drafts on, writes drafts in your Gmail; nothing is sent from your Gmail without your tap | Google, with your own client and sign-in |
| Classroom → notes | Classroom posts and the text of their attached files, to write the notes | the AI service you picked; read from Google with your own client |
| Mail digest | the text of the mail you chose for the digest (senders, domains and labels you named; on a school or work account, your own domain; with a Gmail search set in `mail_digest.query`, the mail it matches, where personal mail is only counted by the AI, never summarised). Other mail, mail marked confidential (in its subject, anywhere in its text including standard confidentiality footers, or its labels) and your never-read list: nothing, they're only counted on your computer. Work or school mail may be covered by your institution's email policy; Kurooto never summarises mail marked confidential with the AI you picked | the AI service you picked; read from Gmail with your own client |
| Email in (off by default, `/mail in on`) | the text of mail you forwarded to your own +kurooto address (from your own address, or addresses you listed) or gave your Email in label, for the AI to summarise into a note and list its dates; with no tools. Mail to +kurooto from anyone else, mail marked confidential and your never-read list: never opened | the AI service you picked; read from Gmail with your own client |
| Mail digest, confidential mail in local mode (opt-in, `mail_digest.confidential` = `local`) | nothing: a model on this computer (Ollama, 127.0.0.1) summarises it; the summary stays in Kurooto's data folder (`mail/confidential/`, readable only by your user account), out of your notes, Telegram (a count only), Profile sync and Backups (unless `backups.confidential_mail`) | stays on this computer |
| Email reply drafts | the draft reply, written into your Gmail Drafts; sent only when you tap Send | Google (your Gmail) |
| Agent plan calendar | the time blocks (title and time), in Kurooto's own calendar | Google (your Google Calendar) |
| Dreaming | nothing: it reads Kurooto's own log, your requests' titles, what calls searched your notes for (kept 8 days) and your notes. Consolidating (`dreaming.consolidate`) compares what Kurooto remembers (gists, how-to-help-me lines, your recent daily notes and project meetings, open deadlines) by rules on this computer; its state file (`dreaming-consolidate.json`) holds only references and keyed hashes, and a dropped gist's words are kept sealed with the memory ledger's key for its Undo. Its second opinion on near misses (`dreaming.consolidate_ai`): `local` (the default) asks the model on this computer; `main` sends the two lines (how-to-help-me lines and note lines only, never a gist) to your AI, at most 8 pairs a night; `off` asks nobody. Folding what it learned into your profile (`dreaming.fold`) reads your chats, call lines, requests and journal by rules on this computer; the lines waiting for your Keep are kept in `dreaming-fold.json` (owner-only), and a line you Keep goes into your profile or how-to-help-me note (so along with every AI request); its second look (`dreaming.fold_ai`): `local` (the default) asks the model on this computer, `main` sends each line the rules picked (never health, money, passwords or other people) to your AI, at most 8 a night. Tuning effort, AI order and Start-by sizes is arithmetic on its own records. With `dreaming.propose_prompts` on (off by default): a skill that keeps going wrong, the requests that went wrong (asked, and your words about them) | stays on this computer; with `dreaming.consolidate_ai` or `dreaming.fold_ai` = `main`, the AI service you picked; a proposed fix to the AI that takes second looks (`learning.brain`), else the AI service you picked |
| Set up from what you say | nothing: rules on this computer read what you send, and its nightly pass (`infer.sweep`) your chats with Kurooto and your journal and daily notes. A line the rules can't read but that looks like a project, a class, a routine or a short name can get one more try (`infer.sweep_ai`): `local` (the default) asks the model on this computer; `main` sends that one line to your AI, at most 10 a night; `off` asks nobody | stays on this computer; with `infer.sweep_ai` = `main`, the AI service you picked |
| Handwritten notes | nothing when a model on this computer reads them (Local models: the vision model on 12 GB graphics cards, the helper model on 8 GB ones, or `handwritten.local_model`); otherwise the scans and photos, unless you turn that off (`handwritten.cloud` = `false`: they wait for a model here). Linking a written-out note to your other notes (`handwritten.link`, on): the note's text, the titles and opening lines of the notes it may relate to, your subjects' names and the opening of their course pages, and when it was written | Google (Gemini, your key) only when no model here reads them; the linking to the AI service you picked (the concept graph's second-look AI when that's on) |
| Books and PDFs | nothing while reading: the PDF's text, Tesseract and a local vision model all work on this computer, and the books, their text and the index notes stay here (the books outside your notes). Only with `books.gemini` on (off by default; books may be copyrighted): pictures of the pages nothing on this computer could read. When the AI writes your notes: excerpts of your books (the pages on the topic), Classroom materials and your notes, in the mix you chose (`course_sources`) | Google (Gemini, your key) only with `books.gemini`; the excerpts to the AI service you picked |
| Books and PDFs: setting up | installing Tesseract (`/books setup`) downloads it from winget (Windows) or Homebrew (macOS); on Linux it only opens the install page. Nothing of yours is sent | Microsoft's winget sources or Homebrew |
| Google Calendar | nothing leaves; Kurooto reads your own calendars (read-only). Other people's calendars shared with you are left out | (read from Google) |
| Mail digest by email | each mail digest's text, sent from your Gmail to your own address only (never another recipient); not sent if it mentions confidential material | Google (your Gmail, to yourself) |
| Drive upload | the files you send yourself, into a Kurooto folder in your Drive; nothing is shared | Google (your Drive) |
| About you | the reports you add stay on this computer (Kurooto's data folder, not synced); building the profile sends them to the AI you picked, and its short "In brief" part goes along with every AI request | the AI service you picked |
| Research | your fields, keywords and searches, arXiv searches you wrote in arXiv's own words included (never your notes). Runs kept in your repositories (`runs/index.csv`) and `research.save_note` stay on your computer | the sources you pick: arXiv, bioRxiv/medRxiv, PubMed, feeds (all public) |
| Research: a project from a repository (`/project add`) | git fetches a GitHub repository you named (your own git sign-in for a private one; Kurooto sends nothing of yours and never asks for a token). With `gh` signed in (`repo_projects.github_extras`): the repository's description, topics, open issues and milestones are read. With Chat on, to write the project note: its README, `docs/`, the file list, manifests, licence, `CITATION`, the first pages of a paper in it, recent commit messages with the authors' names (no emails), issues and milestones, and the names of your courses and projects. Anything that looks like a key is taken out first; files named like secrets (`.env`, keys, `credentials`, `token` files, `.ssh/`, `secrets/`) are never copied or read; nothing in it runs. Its README and docs go to the concept graph like a book (to the graph's AI) | `github.com` (git), `api.github.com` (gh); the AI service you picked |
| Research: Zotero (a paper you tap) | the paper's public details: title, authors, abstract, date, link, arXiv id or DOI | the Zotero app on this computer (its connector, `127.0.0.1:23119`), or Zotero's web API (`api.zotero.org`) with your key |
| Research: "Remind me tomorrow" by call (Phone calls on) | the project's name, as the call's reason | your call line (Cloudflare, Gemini Live), like any call |
| Research: `kurooto watch` | the command's name, exit code, duration and last lines (`--lines 0`: none) | Telegram (your own bot), like any message |
| Terminals | nothing by themselves (see [Your own code and terminals](#your-own-code-and-terminals)) | stays on your computer |
| Kurooto Terminal | nothing by itself; getting kitty or fish (only when you say yes) downloads them from their official GitHub releases. What you type to your AI's program goes to its service, as when you run it yourself | stays on your computer |
| Your add-ons | nothing by the feature itself; your add-ons' own code can do anything Kurooto can, so they send whatever they're written to send | wherever your add-ons send it |
| Add-ons by link (official ones too) | adding or updating one: git fetches it (handed to git); after that, its code may reach only the hosts on its card, and the programs on its card send what they send | the git address you gave (github.com for the official add-ons); the hosts on its card |
| Study tracker: telling you're away | nothing: the idle check reads input interrupt counts (`/proc/interrupts`), the cursor position (Hyprland) and whether a screen locker runs; never what you type, and none of it is kept | stays on your computer |
| Calm by default (on by default) | nothing: what's recorded about each message that came by itself (when, why, the setting, what it was about, its first 300 characters (forgotten after `privacy.keep_days` when you set it), whether you tapped or answered it) stays in `calm.db` in Kurooto's state folder for 45 days, and a message waiting for the evening bundle is kept in full until it's sent. It goes into Backups like the rest of the state folder, never into Profile sync; `notify.calm.on` = `false` records nothing | stays on your computer |
| Setup page progress | nothing: which steps of the setup page you finished or skipped, the seconds spent on each and how often you opened it stay in `setup.json` in Kurooto's state folder, never what you typed; `kurooto doctor --bundle` puts them in the zip it saves on this computer | stays on your computer |
| Wrong button and test cases | nothing: what you typed, what Kurooto did and a snapshot of the settings that decided it stay in Kurooto's state folder (`cases/`), never in Backups, Profile sync or `kurooto doctor --bundle`; cases you didn't review are forgotten after 30 days (`cases.keep_days`, or `privacy.keep_days` when you set it). The monthly look back shows phrasings back to you on Telegram, where they came from. `kurooto cases export` writes a file on this computer; sharing it is up to you | stays on your computer |
| Local AI models, the offline helper (`local_helper`: its quick decisions and offline answers; only its model's download goes out, made by Ollama), Reminders, Deadlines (with recurring quizzes, the not-interested list, exam mode and start-by dates), Subjects, Doubt queue, First-week quests, Study tracker (and its daily note section), Quick notes and prompts, Stay awake on charger, Sync everything (each sync sends what its own feature sends), `kurooto top`, `kurooto runlog`, notes brain timelines, course pages, weekly checkup and checkup line (GBrain's doctor, run read only) and reading its contradictions report, run compare (the Research add-on) | nothing | stays on your computer |

## Where requests go

Every request Kurooto makes on the internet goes through one place that counts it (the host, the feature, how many
requests and bytes, per day) and checks it against this list. `/egress` shows the last 7 days. Only counts are kept
(`egress.json` in Kurooto's state folder, 30 days), never what was sent.

| Host | What reaches it |
|---|---|
| `api.telegram.org` | Telegram |
| `generativelanguage.googleapis.com` | Gemini, with your key (chat, Voice's Live at the desk, voice notes, handwritten notes, books, the notes index, checking the key) |
| `oauth2.googleapis.com` | Google sign-in, and taking it back (`kurooto uninstall --revoke`) |
| `classroom.googleapis.com` | Google Classroom |
| `gmail.googleapis.com` | Gmail (mail digest, drafts) |
| `www.googleapis.com` | Google Drive and Google Calendar |
| `api.github.com` | Notes sync and Profile sync (checking your repository); gh reading a project's issues and milestones (Projects from repositories, when gh is signed in) |
| `github.com` | Projects from repositories (git fetching a repository you named); downloading Git (Windows), Tectonic, kitty and fish; Voice's models (Kokoro, Silero VAD; openWakeWord's feature models only for your own wake word model) and Voice ID's speaker model, only when you set Voice up |
| `huggingface.co` | Voice: downloading the speech-to-text model (faster-whisper) and the Piper voice, only when you set Voice up; nothing of yours is sent |
| `release-assets.githubusercontent.com` | GitHub's file server for release downloads (Voice's models, Voice ID's model): GitHub's release links redirect there; only when you set Voice up, nothing of yours is sent |
| `media.githubusercontent.com` | Face presence: downloading its two models (OpenCV's model zoo: YuNet and SFace, pinned and checked by sha256), only when you set it up; nothing of yours is sent |
| `api.cloudflare.com` | Phone calls: setting up your call line |
| `.workers.dev` | Phone calls: your call line (any address under it) |
| `ntfy.sh` | Phone calls: ringing your phone |
| `nodejs.org` | Phone calls: downloading Node.js to set up the call line |
| `ollama.com` | Local AI models: downloading Ollama |
| `registry.ollama.ai` | Local AI models: how big a model is, before you download it |
| `export.arxiv.org` | Research (arXiv) |
| `api.biorxiv.org` | Research (bioRxiv, medRxiv) |
| `eutils.ncbi.nlm.nih.gov` | Research (PubMed) |
| `api.zotero.org` | Research: a paper you tap into Zotero (its public details: title, authors, abstract, link), with your Zotero key; not used when the Zotero app on this computer takes it |
| `avtarfr.github.io` | Updates and the list of withdrawn versions |

**Addresses you gave are yours** and always allowed: your calendar's private link, class calendars you subscribed to,
the feeds you added to Research,
the AI service you entered (a custom OpenAI-compatible one), your call line and your own ntfy server, and the public
pages your AI reads for a request (its web reading tool). This computer (`127.0.0.1`) is always allowed and never
counted: nothing leaves.

**Programs that go online by themselves** are counted as "handed to" them, with the feature; Kurooto doesn't look
into what they send: git (Notes sync, Profile sync, Add-ons by link, Projects from repositories), gh (a project's
issues and milestones), npm and wrangler (setting up your call line), agy and Claude
Code (AI requests), Ollama (downloading a model), GBrain (making the index with Gemini, or your own brain's models),
Tectonic (LaTeX packages), uv or pip (Voice's and Face presence's Python packages, from PyPI, when you set them up), and installers
(winget, Homebrew, Flatpak, npm, Bun, a vendor's install script). Where they
send it is in the tables above.

**Enforcing it** (`privacy.egress`): `record` (the default) counts everything and marks a host that isn't on the list
"not on the list" without stopping it, because an add-on or an address changed in settings can reach hosts this list
can't know of. `enforce` refuses those: the feature fails with a message naming the host. To allow one, add it to
`privacy.allow_hosts` (`["feeds.example.org"]`; `".example.org"` allows every host under it). `off` checks and counts
nothing. Your add-ons' own code is covered only when it makes its requests through Kurooto's (`core/egress.py`).

**Add-ons by link** are fenced apart (`core/fence.py`), in every mode: their code may connect only to the hosts on the
card you agreed to and start only the programs on it; anything else is refused and shows in `/egress` as blocked for
"add-on <name>". A program on the card that goes online by itself is counted as handed to it. It's a fence, not a
sandbox: code you agreed to runs with Kurooto's access, and code written to get around a fence can.

## Free tiers and terms

**A free Gemini API key** (Google AI Studio's free tier):
- Google may use what you send and what it answers to improve its products, and human reviewers may read it.
- You must be 18 or older.
- In the EEA, the UK and Switzerland you need a paid key (billing turned on).
- Phone calls and voice notes always go through Gemini, whichever AI answers your messages (a call turn by turn can
  use the model on your computer instead: `calls.turn_brain` = `local`).

If you don't want that, use a paid key: on paid tiers Google doesn't use what you send to improve its products. Or
keep those features off, or use local models where offered.

**Antigravity (agy):** Kurooto runs Google's official agy program on your computer, signed in as you, and never touches
its sign-in token. Google's answers differ on whether other tools may start agy unattended, so there is some risk to
your Google account. For tools like Kurooto, Google recommends a Gemini API key.

Every other AI service you pick (Claude Code, a custom OpenAI-compatible one) works under its own terms and your
own account. An extra Claude account (0.7.0) sends to Anthropic like your usual one; its sign-in stays in Kurooto's
data folder (`claude-accounts/<name>/`, never read or copied by Kurooto, out of backups unless `backups.secrets`). Kurooto no longer offers FreeLLMAPI, which pools other providers' free tiers; one set up with an earlier
version keeps working and shows as "Another OpenAI-compatible service".

## Google: what each permission allows

Kurooto signs in to Google with your own "OAuth client" (made in your own Google Cloud project), so no one else's app
ever holds your Google access. Each Google feature asks for only the permission it needs, when you set it up:

| Feature | Google's permission | What Kurooto does with it |
|---|---|---|
| Google (Classroom) | see your Classroom courses, your coursework and announcements (read-only) | due dates into Deadlines, new posts to Telegram |
| Gmail drafts, Email reply drafts | manage drafts and send email | writes drafts; sends one only when you tap Send |
| Classroom → notes | see your Classroom course materials; see and download your Google Drive files (read-only) | reads materials, coursework and announcements, and opens only the Drive files attached to or linked from a post. Changes nothing |
| Mail digest | read your email (read-only) | reads only the mail you choose for the digest (rules, your own domain, or your Gmail search); the rest it counts by its sender, subject and labels, on your computer. Can't send, delete or mark anything |
| Agent plan calendar | make secondary calendars and manage their events | makes one calendar of its own, "Agent plan", and writes only there; it can't see or change your other calendars |
| Google Calendar | see your calendars (read-only) | reads your own calendars and the ones you subscribed to, the next two weeks; calendars other people share with you are left out. Changes nothing |
| Mail digest by email | send email on your behalf; see your email address | sends each mail digest to that account's own address and to no one else. Can't read your mail |
| Drive upload | see, edit, create and delete only the Drive files it uses | makes one folder, "Kurooto", and uploads the files you send yourself there. Can't see your other files; shares nothing |
| Every account (from 0.5.1; before, any but the first) | see your email address | to show which account is which ("school: sam@school.example") |

**Several accounts.** Each Google account you add signs in on its own and is asked only for the permissions of the
features you give it (`/google` lists them). Its sign-in is kept in this computer's keychain like the first one's;
`/google forget <name>` removes it from this computer.

**Mail marked confidential is never read.** Work or school mail may be covered by your institution's email policy
(many forbid forwarding confidential messages, and institutional mail belongs to the institution). If a mail's
subject, its text (all of it, footers and quoted replies included) or a Gmail label's name says "confidential", "do
not forward", "restricted", "private and confidential", "privileged and confidential" or "proprietary and
confidential", or carries a standard confidentiality footer ("intended solely for the addressee", "if you are not the
intended recipient", "this e-mail ... is confidential / may be privileged"), Kurooto only counts it, even from a
sender or label you chose: it isn't sent to the AI, summarised, or answered with an AI draft. (To spot a marking in
the text, Kurooto reads it on your computer, then drops the mail in memory without keeping it.) The same goes for
everything on your never-read list (`/mail never`). This is on by default (`mail_digest.skip_confidential`); tune the
list in `mail_digest.confidential_words`.

**Optional local summaries.** With `mail_digest.confidential` set to `local` and Local AI models on, a model on this
computer (Ollama, 127.0.0.1) summarises that mail instead. Only the summary is kept, in Kurooto's data folder
(`mail/confidential/<date>.md`, readable only by your user account); the dashboard shows it on this computer. It
isn't in your notes, on Telegram (which gets a count only), in Profile sync, or in Backups unless you turn on
`backups.confidential_mail`. Dates found there are offered to you (titles and dates only) and never added by
themselves. No AI reply drafts for it, ever.

**Copies kept on your computer:** downloaded Classroom files (Kurooto's data folder, `classroom/`); the text of the
mail you chose, only until the digest is written (state folder, `mail-digest/`); and the sender, subject and a short
excerpt of digested mail for 30 days, so a reply draft can answer it.

To withdraw a permission: your Google account → Security → Third-party access → your project.

## The AI's tools

Tools add no new destination: what a tool returns to the AI (a note's text, your reminders or deadlines) goes to the
AI service you picked, as the notes it reads always did. AI requests can't answer your questions or approvals: those
tools exist only on calls, with you.

- `kurooto mcp` (how agent programs reach the tools) talks only to Kurooto on `127.0.0.1`, with a key that is good for
  the tools and nothing else; it changes at every start and is kept in an owner-only file in Kurooto's state folder
  (`tools-access.json`).
- What the AI may read on this computer (Kurooto's own tools and agy alike): your notes, Documents, Downloads and
  Screenshots folders, and Kurooto's copies of Classroom and mail; hidden files (like `.git`) are left out. What it
  reads goes to the AI service you picked. It may write only in your notes folder, your Classroom course files and,
  with add-ons on, your add-ons' `skills/`; Documents and Downloads stay read-only. Before it changes existing text
  (`edit_note`), the previous version is kept in Kurooto's state folder (`note-history/`, the last 20 per file); Notes
  sync's history has every version too.
- The AI may read public web pages (GET only). It never fetches this computer or your local network, so a page or a
  note can't steer it into your router or other programs here.
- agy's settings file is changed only by adding (after a backup; your own rules stay): `mcp(kurooto/*)`, `read_file`
  and `write_file` for the folders above, `read_url(*)`, harmless commands (cat, find, git, grep, latexmk, ls, rg and
  similar; never `kurooto` or `sed`), and non-workspace file access if you hadn't set it. Kurooto asks before adding
  anything (Approve / Deny), except when you test agy on the setup page, which says what it allows.
- A long agy request is written, for the length of the run, to `.kurooto/requests/` inside your notes folder (a hidden
  folder Notes sync ignores, so it's never uploaded), then deleted.

## Questions and approvals

Questions are delivered on the channels you set up (Telegram, the phone app, the desktop) and stored on this computer
in the state folder (`ask/<id>.json`), deleted 30 days after they're answered or expire
(`ask.keep_days`, or `privacy.keep_days` when you set one). The events log records when and where you answered, not what.

## Kurooto's mind log (Brain)

Brain (0.8.0, off until you turn it on) keeps a log of what Kurooto saw and decided, and its scores, in the `mind`
folder of the state folder, on this computer only:

| What | Kept | Leaves the computer? |
|---|---|---|
| The mind log (`log.db`): ids and numbers only (a deadline added, a call missed, a button tapped, an AI request ended), and Kurooto's own decisions with their reason (up to 300 characters); never the words of a message, a reminder, a title or anything you typed | until you delete it (turn Brain off, then Delete Brain's data) | no; not in backups or Profile sync |
| The gate's state (`mind-gate.json` in the state folder): counts of messages sent, the touches used, the week's feelings, which kinds are muted, messages held until their time (their text, at most 200), the originals behind an Undo (7 days) and the last 60 things it did (what, why and the first 80 characters of a removed sentence, for `/mind gate`) | until you delete it (Delete Brain's data); held messages and Undo originals go by themselves | no; not in backups or Profile sync |
| Brain's history (`history.db`; 0.8.1, every source 0.8.7; `mind.backfill.on`, off, and `mind.backfill.<source>`): what Kurooto kept before Brain was on, read once from its event history, AI request history, deadlines, check-ins, quizzes, calls, request index and study time | ids and numbers only, under their real dates: kinds, counts, efforts, durations, done or not; never words, titles, names, transcripts or anything about health or money (subjects only as a code) | stays on your computer; not in backups or Profile sync; `/mind backfill forget` removes it |
| Brain's scores (`score.db`): filled by the parts of Brain as they run (forecasts, promises, experiments) | the same | no |
| Where the log has got to (`anchors.jsonl`), also shown in the morning message | the same | no |

## How long it's kept

What Kurooto keeps of your conversations on this computer stays until you say otherwise: set `privacy.keep_days`
(e.g. 30) and it's forgotten after that many days, every night (0, the default, keeps it until you forget it): call transcripts and calls that went on as text, AI requests and their answers
(the time, AI and effort stay, without the words), Chat's recent turns, answered questions, Wrong-button cases you
didn't make test cases, the words of messages that came by themselves, the search index of past requests, and log
lines. `/forget 7d` forgets the last 7 days now; `/forget all` forgets everything, after a confirm button (your face
model too, if you enrolled one). Face presence's template stays until you forget it (`/face forget`); its camera frames
and other people's faces are never kept at all. Your notes
folder is never touched (a voice note's recording is saved there, so it stays), nor the event log, which holds times,
counts and names but never what you typed or what was answered. Your call line holds a call's transcript only while
the computer is off and hands it over when it's back. Backup zips you made before keep what they had.

**Gists.** As the words of a call, an AI request or a chat fade (`privacy.keep_days`, `/forget`), it settles into one
line of what it decided or did, made by rules on this computer from Kurooto's own records: for a call, what it was for
and what its tools did (a reminder's time and wording, a deadline's title; never what a tool read); for an AI request
of yours, its title (the first 80 characters of what you asked), how it ended and its run receipt, never the answer;
for a chat turn, its request's name. A line that looks like a health, money or password detail keeps only its kind.
Gists stay in the memory ledger (below; never your notes or Profile sync) for good, or `privacy.gist_days` days when
you set it. `/gists forget 3` drops one, `/forget
all` asks whether they go too, `privacy.keep_gist` = `false` makes none. Only with `privacy.gist_model` on and Local AI
models on does a model on this computer read a call's transcript to add one sentence; a cloud AI never does.

**The memory ledger.** Everything Kurooto remembers is in one store, `ledger.db` in its state folder, always encrypted
(not only with Profile sync): the gists; open threads (what you said you'd do, in a message or on a call, and tasks you
started; never from a sentence about health, money or passwords); the dated lines Kurooto keeps in your how-to-help-me
note; your daily notes' headings and lines (a health, money or password line is left out); your project notes'
meeting lines. Each row's words and where it came from are sealed with AES-256-GCM under a 256-bit key made on first
use and kept in your system's keychain as `ledger.key` (Windows Credential Manager, macOS Keychain, the Secret Service
on Linux; the owner-only `secrets.json` where there's none, or when Kurooto starts at boot on Linux). On disk stay only
each row's kind, its times, a thread's state and keyed hashes (so a note line you forgot isn't read back in); search
decrypts into memory, so no index of your words is written. If the key can't be read, nothing is shown or written,
and a new key is never made over rows an older one sealed. The ledger and its key are never in Profile sync or the
diagnostics zip; Backups leave the ledger out unless you turn on `backups.memory` (it stays encrypted in the zip and
opens only with its key, which `backups.secrets` carries). `/memory forget 3` forgets a row, `/forget 7d` and `/forget
all` cover threads (and gists when you choose), `/memory export` writes the gists and threads to a note in your notes
folder; your notes stay the source of truth.

## Your own code and terminals

- **Your add-ons** run your own Python code inside Kurooto, with its access to this computer. Only use add-ons you
  wrote or trust; `overlay.code` off keeps their skills, prompts and settings and skips the code.
- **Add-ons by link** (`kurooto addons add`) run someone else's Python code the same way, after you've read their card
  (what they add, the hosts they may reach, the programs they may start) and said yes. They load only while their
  files are the ones you agreed to, at the commit you agreed to; an update shows what changes and asks again.
- **Terminals** in the dashboard are real terminals on this computer: anyone who can open your dashboard can type into
  them, so only turn them on if you're the only person who uses this computer. The dashboard only answers this
  computer, needs a key only its own page gets, refuses other websites, and on Linux checks that every request comes
  from your own user account. What you type into the AI program's terminal goes to that program's service, as when
  you run it yourself.

## Secrets

Your bot token, keys, tokens and links are kept in your system's keychain (Windows Credential Manager, macOS Keychain,
the Secret Service on Linux), or, where there is none, in a file only your user can read. They're never written to
logs. `kurooto doctor --bundle` blanks them out (and names, addresses and folders) before saving anything.

- **Starting at boot** (Linux, opt-in: `kurooto autostart boot` or Settings → Starting): your keychain is locked
  until you log in, so Kurooto's keys are kept in its owner-only settings file (`secrets.json`, readable only by your
  account) instead. `kurooto autostart login` moves them back.
- **Backups:** with `backups.secrets` on, your keys are copied into each backup zip (`secrets.json`), in plain text;
  anyone who gets the zip can use them. Off by default.
- **Your call line and Telegram:** if you approve "going offline" messages from your call line (asked once), your
  Telegram bot's token and your chat id go to your call line on your own Cloudflare account, beside your Gemini key.
  With them the line can send messages as your bot (it only sends "Kurooto has been offline since ..."). Set
  `notify.presence.line_telegram` to `false` and they're deleted there at the next sync.
- **Profile sync:** your keys also go to your repository, encrypted with your passphrase (AES-GCM, with a key from
  scrypt). The passphrase is never stored; this computer keeps the profile's data key in its keychain, like your other
  keys, so it can save on its own. Never in the profile: this computer's dashboard key, and the reports you added in
  About you.

## Your phone

The Android app keeps its pairing (the call line's address, its device key, the ring messages' key) in its private
storage. Nothing personal is built into the app. The iPhone web app keeps its device key in Safari's storage for the
Home Screen app. Unpair a phone with `/phones` → `/unpair`, or on the dashboard's Phone tab. A lost phone holds that
pairing and the ring messages' key: `kurooto rotate` gives your call line new keys (they go to your own Cloudflare
account, as on every setup), and the line then forgets every phone paired before, so the lost one can't call, be
called or read new messages.

Answers and chat messages from the Android app are sealed with the same key as the ring messages. That key keeps them
from ntfy, not from your call line: the line holds it too (it seals the ring messages and gives it to each Android
phone when it pairs), so your call line, on your own Cloudflare account, could read them, also while they wait there
for this computer. Only what Reminders with the lid shut, the Today list, Systems and the Notes map, and the Brain hand over is
sealed with keys that only your phones hold.
The iPhone app's answers travel over HTTPS with its device key. Each answer and chat message can be used once (it
carries a random number and the time it was sent). Files shared while this computer is off wait on your call line as
they are (not encrypted there beyond Cloudflare's own storage). The Android app keeps the chat and what waits for
your computer in its private storage; unpairing deletes them.

## Removing it all

`kurooto uninstall` removes Kurooto's settings and data from your computer (your notes folder is kept). Your call
line, Google client, notes repository and the `kurooto-profile` branch are on your own accounts, and backup zips are
in the folder you picked: delete them there (see the manual's Uninstall).

`kurooto uninstall --revoke` first takes back Kurooto's access, which means asking each service: Cloudflare to delete
your call line (with its keys and stored data, the Telegram token and chat id it may hold included) and then to sign
Kurooto out; Google's revoke endpoint, sent each sign-in's token, which is how a token is revoked; Telegram to drop your
bot's webhook, waiting messages and command menu. Nothing else is sent. It then removes Kurooto's keys from your
system's keychain. The GitHub token, the Gemini key, the bot itself and the Google client are yours to delete; it
prints where.

| Reading files from the scratch folder (0.8.0, `sorter.read_files`, off) | nothing: the text is read on this computer into a note; the note is read by the graph like any note | stays on your computer |
| Copies among notes (0.8.0, `sorter.duplicates`, `integrate.duplicates_all`) | nothing: compared on this computer, no AI | stays on your computer |
| Find files (0.8.0, off) | nothing: a local index of the folders you choose; only a file you tap Send on goes anywhere (your own Telegram, or Drive) | stays on your computer |

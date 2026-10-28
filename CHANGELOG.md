# Changelog

## 0.9.0 (unreleased)

- **Files reach the phone app too** (`files.to_app`, on). With the app's chat getting Kurooto's messages
  (`notify.app_chat`), a file it sends you (`kurooto send`, the AI's file, a long answer, a grocery order's screenshot
  from an add-on) comes to the chat as a link as well as to Telegram; one reply says both. A file too big for Telegram
  goes to the chat. Off: Telegram only, as before.
- **LaTeX to PDF for your AI** (`tools.latex`, on). A request that writes LaTeX can now get its PDF: the new
  `compile_latex` tool compiles a copy with shell escape off and answers with the PDF or the first errors. The PDF goes
  beside the `.tex` in your files folder, else into it, never into your notes when a files folder is set; your AI is
  told to write the documents it makes there too.
- **Fix: the call line no longer drops for nothing.** A heartbeat that looked silent because this computer was busy
  now gets one more ping and five seconds before the line is called dead (about 35 needless reconnects a day before);
  a late heartbeat is logged with how late it was.
- **Fix: the evening check-in doesn't ask what a class you missed covered.** A class with a catch-up task is
  mentioned as missed (the catch-up is on your list), and no study log is asked for it.

## 0.8.18 (2026-10-29)

Kurooto keeps its eyes and ears shut while it sleeps, stays up while you're at the desk, and anyone's look opens a conversation.

- **Asleep, its camera and microphone are off** (`mind.sleep.senses_off`, on). While Kurooto sleeps, Face presence
  pauses ("Kurooto is asleep") and Voice stops listening (the Body add-on's desk phone stops its camera and microphone
  too). Its name can't wake it then: the new **/wake** does, and so does a message, a tap or a call from you. Woken, they
  come back; when it dozes off again, they go off again. Off: Voice keeps listening at night and its name wakes it, as
  before.
- **It doesn't fall asleep while you're at the desk** (`mind.sleep.desk_holds`, on). With Face presence seeing you at
  this computer (your face, or your keyboard and mouse), its night waits, and starts 15 minutes after you leave
  (`mind.sleep.desk_after_min`), at most at the window's end. Once it's asleep, sitting back down doesn't wake it; after
  you wake it, the desk keeps it up again.
- **Anyone's look opens the conversation** (`voice.listen.look_anyone`, on). Not only your face: a friend looking at it
  can talk to it, while people talking to each other without looking at it stay ignored. Face presence reads only where
  their faces point (their head, or their eyes against your calibration), never who they are. A guest is still a
  guest: chat only, no tools, none of your data.
- **In company, a look and its name count even misheard** (`voice.listen.look_in_company`, on). With a friend in view,
  its name had to be first and transcribed exactly, so "Kurooto, close your eyes" could be lost to a garbled name.
  After a look, its name first or last spelled any way is enough.
- **A look works while it's drowsy or woken at night.** Only asleep stops it now (it used to stop in the half hour
  before its night too).
- **Nothing is done twice when Live stumbles.** At the desk, Gemini Live started a grocery order, then didn't answer
  in time; the turn went to your AI the usual way, which ordered again, and you heard "An order is already going".
  Now, once Live has run a tool in a turn, a failure says that tool's result in Kurooto's own voice, and the turn
  never goes to your AI or an add-on's plain words.
- **One add-on can't blank the Features page.** An add-on whose setup form had no links list made the whole page fail
  to draw; the page now copes.

## 0.8.17 (2026-10-28)

Voice you can talk to: it finishes what it says, hears you over the room, answers sooner, opens when you look at it (by your eyes), and can answer through Gemini Live; calls keep going on Back and save every transcript; plans that follow what changed; messages one by one; and the AI knows when it recognised you.

- **Back no longer hangs up a call** (Android app). Back during a call now leaves it running behind your other apps,
  the way a phone call does, with an "On a call with Kurooto" notification: tap it to go back to the call, or use its
  **Hang up**. Only Hang up ends a call. The app holds the microphone for it meanwhile, so Kurooto still hears you.
  Back while a call rings just closes the ringing screen: it keeps ringing, and the notification still answers or
  declines.
- **Every call's transcript reaches your computer.** A call whose screen closed some other way than Hang up (Back
  before this release, a closed browser tab) lost its transcript, and your computer kept thinking you were on a call
  for a while. Now the call page sends the end and the transcript as it closes (the end of a very long call, if it's
  over 60 KB), the app hangs up properly a call its screen was closed on, and the same end arriving twice is kept once.
- **"I skipped all classes" is one step on a call.** Calls can skip several classes, or all of today's, at once
  (`skip_class` takes a list, or "all"; `skip_commitment` the same for commitments), and are told to, instead of one
  tool call per class. The call screen also stops repeating itself: the same note again shows once with "×3", and
  classes skipped one after another show as one line, "skipping Linear Algebra, Probability" or "skipping today's
  classes".
- **Rescheduling plans what's actually due.** Rescheduling the day moved every block blindly: revision for a quiz that
  was that morning, and a lab journal whose deadline had just moved a week out, went first while homework and a quiz
  due the next morning didn't fit. Now each Agent plan block remembers the deadline, quiz or exam it's for; a
  reschedule drops (and names) blocks for something done, over, or moved past "due soon" since it was planned, puts
  what's due soonest first, takes tonight's blocks past midnight into account, and names what's due within a day with
  no block yet. A block for something over or done isn't planned at all.
- **Your order on a call wins.** "Homework first, then quiz prep": reschedule_day takes that order and puts those
  blocks first, and says which part named no block.
- **No more overlapping blocks.** A block planned on a call or with /blocks add that would overlap another goes in
  the first free time after it and the call says the time it got; with no room before 03:00 it isn't planned and the
  call says so.
- **Remove planned blocks** on a call ("remove those", "clear everything after 10") or with /blocks remove, with Undo
  (a button, /blocks undo, or "put them back" on the call).
- **A call only says what it did.** Its instructions now say never to claim something was done unless a tool's answer
  says so; one said "I'm removing those study sessions" with no tool that could.
- **Claude Code stays running for a conversation** (`brain.claude.session`, on): your chat's and voice's turns go to
  one Claude Code kept running for that conversation instead of starting the program for every message, so answers
  start sooner. Same permissions, tools and folders as before; it closes after 10 idle minutes
  (`brain.claude.session_idle_min`), when you change your AI or start the chat over, and if it fails that turn is
  answered the old way.
- **Look at it to talk** (`voice.listen.look_to_talk`, on; needs Face presence on and enrolled): look straight at the
  camera for about a second and Kurooto starts listening as if you'd said its name, so the next thing you say needs no
  "Kurooto". It's your head's direction, not your eyes, judged within tight angles (`voice.listen.look_yaw_deg`,
  `voice.listen.look_pitch_deg`, 15 degrees) for `voice.listen.look_dwell_s`; looking away for
  `voice.listen.look_away_s` before saying anything closes it again. Never while muted, asleep, on a call, or with
  Voice or Face presence off; Voice ID and the chatter rules still apply to what you say.
- **Live at the desk** (`voice.listen.live`, off): your own spoken turns can be answered by Gemini Live, speech to
  speech, in about a second, the way phone calls already work. Only turns Kurooto already decided you said to it, in
  your voice (Voice ID) and while you face it close by, go to Google, as sound; everything else stays as before. The
  conversation keeps one Live session while it's open, tools that need your tap still ask, and if Live can't answer
  the turn goes the usual way.
- **Look at it to talk, by your eyes** (`voice.listen.look_gaze`, on): on the Face page, Get the eye model (2.6 MB,
  MediaPipe Iris) and Calibrate my eyes (three seconds looking at the camera's lens), and a look counts by your eyes on
  the camera, not your head's turn: eyes on the screen below it don't open Voice, and eyes on the lens open it at once
  (`voice.listen.look_gaze_dwell_s`, 0), with the camera looking 5 times a second while Voice listens
  (`face.watch.look_fps`). Only four numbers are kept, in your sealed face model; never a picture. Without the model or
  a calibration it goes by your head's turn as before, and /voice says which. Face presence also works the same with a
  sharper camera (1080x1440): sizes are judged as shares of the picture, and the eyes are read from the full picture.
- **Voice says the whole answer.** Barge-in stopped an answer for good whenever a voice that passed as yours was
  heard over it, even an "mm", a cough or a word to someone else, and the rest went unsaid. Now it goes quiet at once,
  and unless what you said was "stop" or a new question or request, it carries on from the start of the sentence it
  was cut in.
- **Auto gain** (`voice.listen.auto_gain`, on): hearing follows the room. Speech has to stand clearly above the
  room's noise to count (`voice.listen.auto_gain_snr_db`, 6 dB), and a quiet or far voice is brought up to one level
  before it's written out. Inside Kurooto only; the system's microphone volume is never changed.
- **Voice answers start sooner.** The first clause of an answer is spoken as soon as it's written, not after its
  whole sentence; a spoken turn no longer waits for offers that only come as buttons (two close readings, a feature
  that's off), including the local helper's pick; and /voice's speed line now times the routing steps by name.
- **Your words are written out at your first pause** (`voice.listen.early`, on): if you don't go on, the turn uses
  them straight away, and a finished question ends your turn after 0.35 s of quiet instead of 0.7 s. Nothing is sent
  early, and with Voice ID's gate another voice is never written out early.
- **Claude Code can open the pictures a job is about.** A screenshot or photo outside your notes (Interest's look
  at your screen, a picture from the phone) was named in the request but reading it was denied every time, so the
  answer said it couldn't see it. Each such picture is now readable for that job, and nothing else beside it.
- **The evening bundle comes one by one.** What waited all day came as one long message, its buttons numbered and
  merged; in the phone app only the first six showed. Now it's a short header, then each message by itself with its
  own buttons (`notify.calm.bundle_one` brings back the single message). Any app message with more than six buttons
  goes on in a follow-up instead of dropping the rest.
- **Shorter answers** (`jobs.header`, on): the first line repeating what you asked, "[Claude Code · medium] ...",
  can be turned off so the answer comes alone; with `jobs.receipt` off too, nothing but the answer.
- **It knows when it recognised you.** Asked "do you recognise my face?" at the desk, the AI said it had no camera:
  a spoken turn reached it as bare text. Now each one says it was said aloud at the desk, whether Voice ID knew your
  voice, and whether Face presence recognises you in front of the camera (never the pictures themselves).
- **Desk Live can't approve anything.** The call tools it shares included the one that answers approvals, so an
  action that waits for your tap could have been approved by the AI that asked for it. At the desk it's never offered,
  and asked for anyway it says the approval waits for your tap. Desk Live is also told each turn reached it because
  Voice ID and Face presence recognised you (it never sees the camera's pictures).
- **A question said at the desk is never filed as meeting minutes.** Within three hours of a meeting starting, a desk
  question of eight words or more was taken as a voice note of the meeting and never answered.
- **Voice language:** the settings guide now says to set `voice.listen.language`; left to be worked out on each short
  clip, an accent is often taken for another language and Kurooto's name is missed.
- **The Chat page fills its pane.** The list of messages was a short box of about 170 px with the box to write in right
  under it and the rest of the page empty. The messages now take the whole height, with the box to write in at the
  bottom.
- **Searching Settings no longer squeezes rows.** When a search hid a section's first setting, the next one that
  matched was pushed beside the section's heading with no room: its name ran down the right edge one letter a line and
  its box was tiny. Every matching row now lays out under the heading as it does without a search.
- **A narrow window and back keeps what you had open.** Making the window narrow (tiling it to half the screen) and
  wide again opened the Features page (or whichever tab the narrow layout last showed) over a board that had no page
  open, and closed pages such as Chat or AI jobs. The wide board now comes back as you left it: the same page, or none.
  A tab you pick while the window is narrow still opens over the wide board as before.

## 0.8.16 (2026-10-28)

The Brain becomes core: one door for what Kurooto says by itself, sleep on your schedule, dreaming, one being across the dashboard, phone and voice; plus the new call screen in the call, faster and steadier voice, the dashboard's Chat page and narrow windows.

- **Voice no longer crashes Kurooto.** Turning listening off, muting, or a microphone that came and went could close
  the microphone's sound stream while the listening thread was still reading it, and the whole of Kurooto died (a
  segmentation fault in the sound library, seen several times a day with PipeWire). Each sound stream is now opened,
  read and closed by one thread only; stopping just asks it to finish. A microphone that disappears (a PipeWire
  source removed, PipeWire restarted) is opened again after a pause instead of failing, and only one that stays gone
  is reported. Speech plays through a stream of its own per sentence, so a stop can't close it under the player.
- **Sound through PipeWire's own tools.** On Linux with PipeWire, speech now plays through `pw-play` and the microphone
  is read through `pw-record`, separate programs, so a sound driver problem can't take Kurooto down, and listening
  follows your system's default microphone. `voice.audio.backend`: `auto` (the default; PortAudio when
  `voice.listen.device` names a sounddevice microphone, or without PipeWire), `pipewire` or `portaudio` (as before).
- **The phone app's call screen, in the call too.** 0.8.7 redrew only the ringing screen, so every answered call, every
  call you placed from the app and every call answered from the notification still showed the call line's old dark
  green page. The call itself now has the app's style (Phone tab → Switches → **New call screen**, on): Kurooto's badge
  swelling with your voice, who's calling and why, how the call is going, the transcript as bubbles, your mic's level
  and the mic gate, Interrupt and turn by turn's Talk, and Mute, Speaker and Hang up in a floating bar, in your
  wallpaper's colours. The call page still runs the call underneath, so calls work as before, with any call line;
  the switch off brings back the old screens. The ringing screen's buttons no longer cut their words short ("An" for
  Answer on narrow phones), and a phone on its side shows the transcript beside the call.
- **Reading a chat on the dashboard clears the phone's badge.** The app kept its own unread counts and ignored your
  computer's, so a chat read on the dashboard's Chat page (or another phone) stayed unread on the phone. It now takes
  the computer's read marks: its badge and notification for that chat clear too, never marking anything newer as read.
- **Voice answers sooner, and tells you it heard.** A spoken turn used to wait for your AI's whole answer before the
  first word was made; now, when your AI can stream (Claude Code, a Gemini key, Ollama without tools), each sentence is
  spoken as soon as it's written, the first one alone so its sound is made quickly (`voice.speak.stream`). The moment a
  turn goes to your AI a short soft note plays, unless the answer is already coming (`voice.speak.ack`: `tone`, `word`
  for "Hmm." in its own voice, or `off`). When listening starts, the transcriber, the voice and Claude Code's program
  are warmed so the first turn isn't the slow one (`voice.listen.warm_up`, `voice.listen.warm_brain`).
- **Voice measures itself.** Each turn is timed from your last word: written out, decided (the face check included),
  sent, your AI starting, its first words, the first sound made and playing. `/voice` shows the medians of the last
  20 turns; a `voice_timing` event holds each turn's numbers, never words (`voice.listen.timing`).
- **A quicker AI for plain chat by voice, if you want one.** `voice.listen.fast_brain` `local` sends small talk and
  general questions that need nothing of yours to the model on this computer, `fastest` to whichever AI answered
  quickest lately; anything that mentions your things, the time, the web or an action still goes to your AI. `same`
  (the default) changes nothing.
- **Brain's trust decides more of what it proposes.** A study block from the morning line, moving part of a slipping
  deadline's work to tomorrow, a revision pack the evening before an exam, and keeping the quiz cards and
  how-to-help-me lines it wrote at night: below the trust bar for their class it asks with the same buttons as before,
  and each yes counts toward that trust; above it, it does it and says so with Undo, and an Undo sends it back to
  asking. A low mood or beliefs no better than a guess still make it ask first. `/mind` and `/autonomy` list each kind
  with its trust (`mind.act.more`).
- **Brain forecasts when you'll be at your desk and free.** For the next six hours, learned from the activity sense
  and Face presence, scored each hour against what they then show and against "same as yesterday", and rewarded for
  accuracy only (at most 0.05 a day of its reward; nothing about talking to Kurooto counts). Check-ins planned into a
  class or an hour you're usually away move to a likelier time nearby, and calls Kurooto places by itself wait for one
  (`mind.presence_forecast.on`, `.prefer`, `.within_min`). `/mind` shows its accuracy and the next likely-free hour.
- **Quieter ready-made messages, and a polite voice learner.** With Brain on, a nudge a feature sends by itself keeps
  the register's 2 to 4 sentences, plus the question its buttons answer; digests, lists, answers and anything exempt
  stay whole (`mind.register.templates`). The nightly voice learning now waits for the machine like Brain's own heavy
  work.
- **The dashboard works in a narrow window.** Under 1280 px wide (a window tiled to half a 1920 screen) the dashboard
  uses the roomy layout, and since BRAIN joined the board its grid pushed NOTES and the pages into extra rows: on a long
  page such as Features, STATUS, SYSTEMS and BRAIN got no height and NOTES sat alone in a narrow strip. Roomy now places
  each pane by name: STATUS down the left, NOTES wide, SYSTEMS and BRAIN under it, the pages below. With the being as
  the board it shows there too, in place of SYSTEMS and BRAIN, beside NOTES and STATUS. A narrow BRAIN pane keeps its
  region panel as a drawer, a window too short for the panes scrolls, and under 900 px they stack. The dense board
  (1280 px and wider) is unchanged.

- **The phone app's Memory page is as sharp as the dashboard's.** It drew at 1.5 pixels per point and stretched that
  over the phone's denser screen, so notes and their links came out as soft blobs; it now draws at the screen's own
  density with the dashboard's dot size, so the notes are fine points and threads. The other organ pages are unchanged.
- **The Chat page on the dashboard.** Kurooto's messages (reminders, check-ins, answers, what add-ons say, questions
  with buttons) were only in the phone app's chat and on Telegram; the dashboard showed the talk box's answers and
  events without text. The new Chat page (Alt+H, Ctrl+K `open chat`) shows the same chats and messages as the phone
  app, live, newest at the bottom, with Kurooto's buttons, files as links and the app's Waiting for you. A button or an
  answer there is the same as a tap in the app, so a question settles everywhere; a message written there goes to
  Kurooto in the open chat exactly as one typed in the app, and your phones show it as yours. Opening a chat marks it
  read on your computer. It shows what the app's chat holds (not Telegram, Voice or the talk box), needs Phone calls,
  and nothing new leaves your computer. `look.chat_page`.

- **Brain is one being.** One status stream (focus, asleep, how many messages are held, the one deadline it's uneasy
  about, its own mood and arousal; enums and numbers only) feeds the dashboard's being, the phone's Views and add-ons.
  The being's eyes shut in focus time or while it's asleep, a small count by the heart says what's held, and a slow
  glow on the uneasy deadline opens it with a tap (`look.being_status`). Its mood tints the fluid and sets the heart's
  beat; low is only quieter, never sad (`look.being_mood`).
- **One temperament and three honest knobs.** Its mood and arousal set how long its unprompted words are, how a call it
  places opens and Voice's pace for what it says unasked (within 8%), never replies to you (`mind.register.on`). Mood
  sets how much the lab and play explore, arousal how soon it speaks up, and calibration whether its own acts ask
  first (`mind.knobs.on`). Mood never adds a confirm step or slows anything you asked for.
- **Brain's hints in every request.** Each AI request gets the concepts you're shaky on lately and what's on Brain's
  mind, read from its files in under 50 ms with no model call; your read, tone, mood and body state never go in
  (`mind.context.on`). `/mind measures` shows what each part changed in 30 days and the reply latency, information
  only.
- **"AI model", and an Inner life step.** The AI that answers you is now called the AI model everywhere you read it
  (Settings, setup, the wiki); Brain is Kurooto's mind. Setup has an optional step, "Let it grow an inner life", that
  turns Brain on with a plain explanation.

- **Brain dreams about the day.** Each night it offers, in the morning message, 1 to 3 quiz cards for concepts you
  studied that day and are ready for next (written by the model on your computer from your own note), 1 to 3 lines for
  your how-to-help-me note from the day's outcomes (what you undid, what went unanswered, when you told Voice off), and
  one line on what Voice's nightly learning saw ("it woke to your name at the end of a sentence 3 times"). Nothing is
  added until you tap Keep; `/mind` compares your recall on its cards with your own. `mind.dream.cards`,
  `mind.dream.lessons`, `mind.dream.voice`.
- **One worry, not five nudges.** With Brain on, the subject it's most uneasy about gets one morning line ("Uneasy
  about Measure Theory: due Fri, 0 min logged this week, 9 cards due. 25 min at 16:00?", Yes / Later) and that day its
  day-before reminder, "Time to start" and exam mode's practice check-in are folded into it. `mind.study_push.on`.
- **Check-ins that come early.** When the day departs strongly from Brain's forecast (no sign of you two hours past the
  expected wake time while your phone shows you up, or a deadline moved twice), the next check-in comes now, once a
  day, never in a class or while you're asleep. `mind.checkins.surprise`. Add-ons can weigh what's on screen by
  `kurooto.mind.frontier.score`.

- **Kurooto sleeps.** With Brain on, it sleeps while you do and doesn't talk unless woken (`mind.sleep.on`). Its night
  follows yours: bedtime to the alarm, else the night hours, refined by your phone when its screen, light and charging
  sensors are on (asleep early, up late, up early). Asleep, what it starts by itself waits for the morning; reminders and
  calls you set, close deadlines, approvals and answers still come. Its name, a message or a tap wakes it, and it dozes
  off again after 20 quiet minutes. Drowsy half an hour before: nothing said aloud by itself. `/mind` shows it.
- **The Brain's heavy work yields to yours.** The lab, play, plans, skills, the harness and the fine-tune wait while your
  own programs use the graphics card, during a call, on battery or when the computer is hot, and the nightly ones wait for
  Kurooto to be asleep (`mind.yield.on`, `mind.yield.prefer_sleep`). What you ask for never waits. `/mind` shows the
  week's contention minutes.
- **Something sudden is felt at once.** A phone pickup, something close to an add-on's device or a loud room gives an
  orienting jolt: arousal at once and a fresh look at what's on its mind (`mind.stimulation.jolt`).

- **One door for what Kurooto says by itself.** With Brain on, check-ins, Calm's small touches, research watch,
  Dreaming's results, feelings said aloud and add-on ideas now bid at the workspace, and only winners are sent. A
  winner that isn't urgent waits for a natural break (a window switch after a long stretch, a phone pickup, a session
  ending, you coming back), at most 90 minutes; losers wait and bid again, and after 6 hours go into the evening bundle,
  never dropped. Alarms, your reminders, calls, approvals, close deadlines and answers to you go straight through
  (`mind.workspace.arbiter`, `mind.workspace.breaks`).
- **"Why this?" says what Brain did.** Every message Kurooto starts records what it expects (a reply, or that you act
  on it within 2 hours) and what came of it. Why? on Telegram and a new Why this? on the phone app chat's copy say what
  the gate and the door did, what it expected and how many it has sent today (`mind.expect.on`, `mind.why.on`).

## 0.8.14 (2026-10-27)

Voice answers only someone in front of it: a roommate's phone call no longer wakes it.

- **Voice only answers someone in front of it.** A roommate on a phone call across the room could wake it. With Face
  presence on and enrolled, a turn is now answered only when the camera saw a face close to it (at least half your
  usual face height at the desk, `voice.listen.face_near`) and facing it (within about 35 degrees,
  `voice.listen.face_yaw_deg`) while it was said or just after; anything else is chatter, whatever rule would have
  taken it. Your wake word and "stop" / "never mind" work without a face, and typed `/voice` commands are unaffected.
  While Voice listens it keeps the camera looking (the Face card says "voice: who's talking"), never past Face
  presence's own pauses; when the camera can't see, `voice.listen.need_face_fallback` picks the voice rules alone
  (`voice`, default) or nothing by voice (`none`), and `/voice` says which. Only times and counts are kept, in memory.
  The camera's light stays on while it listens, and a video call app can't use the camera then. `voice.listen.need_face`
  (on; does nothing with Face presence off).

## 0.8.13 (2026-10-27)

Voice that knows when it is spoken to and can be cut off, numbers said as words, study packs with what the syllabus cites, and fixes for backups, phone sensors and the phone camera as an eye.

- **Voice: cut in while it speaks.** It used to drop every sound while it spoke (so it wouldn't hear itself), so only
  `/voice stop` could end a long answer. Now it keeps listening: your voice (Voice ID, checked against Kurooto's own
  voice print, made once in memory) or speech clearly louder than its own echo, whose words aren't its own, stops it
  at once, on this computer or on a device an add-on plays it on. "Stop" or "never mind" just stops it, a question or
  a request becomes the next turn in the same conversation, anything else and it stops and listens. Its own voice
  coming back through the room never stops it. Limits: on a speakerphone or at a high volume speak up; a guest can't
  cut in by voice. `voice.listen.barge_in` (on).
- **Kurooto says numbers as a person would.** The speech engine read digits literally: "21:31" with a pause in the
  middle, "0.8.13" as "zero. eight point one three", dates with "slash", "₹3,000" as "rupee three thousand", "12 GB"
  as "gee bee". Times, dates, years, money (₹, Rs, $, €, £, lakh and crore), versions, ranges, percentages, ordinals
  and units are now said in words ("nine thirty-one PM", "three thousand rupees", "twelve gigabytes", "twenty
  twenty-six"), and the waveform follows what's said. Only the voice changes; the screen shows what was written
  (`voice.speak.numbers_as_words`).
- **Short sentences are spoken together.** Each sentence was made on its own, and Kokoro reads a few words alone with a
  hurried, flat tune ("Done." "Sure."). Short sentences are now joined into pieces of up to about 200 characters (the
  first kept short, so speech starts as soon as before) and Kokoro pauses at each full stop inside them
  (`voice.speak.join_sentences`).
- **Sentences no longer run into each other.** The speech engine trims the silence off both ends of what it makes and
  puts a pause back only between parts it joins itself, so sentences made one at a time followed each other with no
  breath. Kokoro's own pause (a quarter of a second after a sentence, a tenth after a clause) is put back between them.
- **Voice: it no longer joins your conversations when you only mention it.** When someone else may be talking (Voice
  ID isn't sure the voice is yours, people talked here in the last minute without talking to Kurooto, or Face presence
  sees two or more faces), its name counts only as a call said first ("Kurooto, what's ...", "hey Kurooto ...", or
  just "Kurooto"); at the end or in the middle of a sentence, or a word that only sounds like it, it's a mention the
  model on your computer judges. You alone, it wakes as before. `voice.listen.careful_name`, `voice.listen.chatter_s`.
- **Voice: a conversation goes on without its name.** After Kurooto answers, what the same voice says within 20
  seconds of it finishing (statements too, not only questions) goes to it, and the conversation stays open that long;
  another voice or two at once end it. In conversation mode the voice that opened the talk gets the same window.
  `voice.listen.follow_s` (0 turns it off).
- **Voice ID keeps a conversation yours.** In a conversation Voice ID knew you opened, a turn it's only "not sure" of
  (inside the margin, not clearly someone else) stays yours, so history, notes and tools carry instead of dropping to
  "only chatting" (`voice.speaker_id.carry_talk`); carry now counts from when Kurooto finished answering. With Face
  presence seeing only your face, a "not sure" voice counts as you (`voice.speaker_id.face_assist`); with "improve over
  time" on, such turns that went well can refine your voice print, with the same caps and undo.
- **Tell it off.** "Stop", "not you", "I wasn't talking to you", "shut up", "be quiet", "go away" or "never mind"
  within about 10 seconds of it opening a conversation or speaking: it stops speaking, closes the conversation and
  says nothing, and notes a misfire (the rule that woke it, never your words). `voice.listen.told_off`.
- **It learns at night from how its voice turns went.** Turns you carried on with and turns you told off are kept as
  flags and numbers only (never words or sound); at 04:10 a small model is fitted, and with 20 turns or more it can
  hold back a borderline opening that looks like past misfires, never "Kurooto, ..." said first. `/voice` and
  `/health` show the numbers. `voice.listen.learn_nightly`.
- **A study pack has the sections your syllabus cites.** A syllabus that gives its readings as a table with a column
  per book ("B&D", "S&S", "BJR&L", spelled out in its abbreviations) and codes (C3, S2.3, D1.11, E3.2.2, C3 P1, SA.3)
  wasn't understood, so a pack fell back to the words of the aim and picked pages like a chapter on process control
  while missing the cited chapters and sections. Kurooto now reads the abbreviations, the code legend, the table's
  columns and inline citations ("B&D S2.3", "S&S 3.5"), matches each book by its authors (even in a misspelt title),
  and puts the cited pages in whole first, up to `studypack.cited_pages` (400), before pages on the topic; a cited
  book's other pages come only from the chapters it's cited in. `INDEX.md` lists every citation and the pages it
  became, or that it wasn't found. A whole syllabus pasted as the aim no longer picks pages by its words.
- **Another subject's notes stay out of a study pack.** A handwritten or other note for another subject (its folder,
  or `course:` or tags in its header) came into a pack when it used the topic's words or the notes brain found it.
- **A study pack goes whole to Drive when you ask.** With Drive upload on, files over 40 MB were still left out, and
  the reply blamed Telegram's 50 MB for everything left out and suggested Drive upload even when it was on. Going to
  Drive, nothing is left out for size now; the reply counts what was left out by its real reason and suggests Drive
  upload only when it's off or not set up. With Drive upload set up but big files off, a pack that left files out
  asks "Send it all as a Drive link?", and the AI's `study_pack` tool takes `to=drive`, so "send it as a Drive link"
  works.
- **A backup could freeze Voice and Face.** A backup ran on Kurooto's main loop, so while it worked, the parts that
  share it waited; and one that met a named pipe in Kurooto's folders (an add-on's stream left behind by a hard stop)
  read it forever, so listening and Face presence never started. Backups now leave out anything that isn't a plain
  file and run on a thread of their own.
- **Face presence: a phone's camera fed in by an add-on works.** Kurooto's own programs no longer count as "another
  program using the camera", a virtual camera can be read while it's fed, and with no camera chosen, one in use
  leaves the next free. A new `face.camera.device` takes effect within seconds instead of after a restart.
- **The phone app's Memory page shows your notes properly.** It framed a fixed ring of feature lights, so the notes
  sat small in the middle and a feature's name ran off the edge; it now frames the notes as they lie, between the
  app's bars, a little larger, with the lights on a ring just round them.
- **The being's YOU lane moves as you speak.** It drew your turn only once the turn was over; while Voice listens it now
  shows the microphone's loudness live, the last six seconds scrolling, and settles into the turn's outline when it
  ends (`look.being_live_waveform`; still, as a sweep, with Remove animations or reduced motion).
- **The voice lanes are smooth waveforms, not blocks.** Both lanes, on the dashboard and the phone, draw a soft
  mirrored shape through the samples instead of a row of bars, so a short utterance no longer turns into a few wide
  blocks.
- **Your phone's senses stopped for 12 hours after any short sleep of your computer.** When a batch of readings had
  to wait on the call line, the phone sent nothing more for 12 hours by the clock, so ten minutes with the laptop
  shut lost Brain its phone senses till the next day (and readings past the phone's 300 were dropped). The phone
  now holds back only while that one batch still waits on the line, and sends the rest once your computer takes it.

## 0.8.12 (2026-10-27)

The being made visible, and what add-ons can do with Face presence, Voice and Brain.

- **The being: sparks you can see, nerves, joined vessels, colour.** The brain showed no sparks at all: they run
  inside it and the solid cortex hid every one; they now show through it in their own colours, and at rest a low
  trickle comes from what Kurooto really does (its body's readings, its own processor use, timers firing, notes
  changing, sound heard; `look.being_resting_sparks`). The vessels and nerves stay joined to the brain and the other
  organs as they turn; the nerves leave the brainstem as a spinal cord and split into fibre bundles with nerve cells,
  lit in a signal's colour. The blood is tinted red, the fluid round the brain pale aqua, the notes each in a clear
  colour, the heart a little fainter, and speech heard that wasn't to Kurooto shows faintly in the YOU lane.
- **The eye follows anyone.** While Face presence has the camera open and a dashboard is in sight, every face in view
  is followed (a number per face, its place and how much it moves: small nods and turns), up to 10 times a second;
  the being's eye looks at one person and moves to another every few seconds, sooner for someone new or someone
  moving, and follows a lone face closely. Places only: nobody else is identified and nothing is kept
  (`face.track.on`, `face.track.fps`; add-ons can follow faces too).
- **Hooks for add-ons in Face presence, Voice and Brain.** An add-on can see who's in view (each face's place, size
  and whether it's you, in memory only) and keep the camera looking while you type, take one thing said through the
  microphone (written out here, never sent), have Kurooto chat with someone the guest way (no tools, none of your
  data), and give Brain a small capped reward for a good conversation. Every pause and mute still applies; switches
  `face.addons.watch`, `face.addons.hold`, `voice.addons.listen`, `voice.addons.chat`, `mind.talk.met`.
- **Brain: another device's senses as a body.** An add-on can report another device's sensors (light, proximity,
  motion, tilt, turning, compass, battery, its temperature, the room's loudness, being picked up, its screen) and
  Brain feels each as its physical analogue on the body map's new face region, while the being's pupil, lids,
  balance organ, cilia, cochlea and coil react; numbers only, in memory, never moving its mood
  (`mind.stimulation.addons`). An add-on's judgement that something caught its interest is felt too, as a
  jolt in the head.
- **Voice: the waveform shows speech that wasn't for Kurooto too.** People talking to each other and noise now move
  the dashboard's waveform as well, as their loudness only: no words ever reach the page. `voice.listen.levels`
  turns it off with the live levels.
- **Voice: an add-on can play Kurooto's voice on another device** (`Voice.add_output`), with this computer's
  speakers taking over when that device can't.

## 0.8.11 (2026-10-27)

Fixes from the first real use of Voice ID and Face presence.

- **Voice ID: Set up from its own page.** With Voice ID on but its files not downloaded yet, the Your voice page
  said to go to the dashboard; it now has a **Set up now** button that downloads them there and shows the progress.
- **Face presence: the near step can be finished.** Sitting close to a laptop's camera, leaning in pushed your chin
  out of the picture before the step counted you as near, so it kept saying "closer" and "partly out of view" in
  turn. The step now asks for 1.25 times your front-facing size, or less when the picture has no room for that, and
  shows how far you are; only your eyes, nose and mouth need to stay in view. "Partly out of view" now says which
  edge and which way to move.
- **Voice ID: the test hears you, and the quiet and far steps pass.** The test gave up 15 seconds after you pressed
  it even when you were mid-sentence, then said it heard nothing; speech that starts in time is now heard to its
  end. A microphone that evens out loudness (automatic gain, EasyEffects) lifted a quiet voice back up, so the quiet
  step never passed; quiet and far now also count when your voice stands less far above the room's noise.
- **Voice ID: the page says when listening is off.** Enrolled with listening off, Kurooto didn't hear you, showed
  no waveform and spoke no replies, with nothing saying why; the Your voice page now does, with a **Turn listening
  on** button.

## 0.8.10 (2026-10-27)

The phone app, rebuilt around chat (the Rail design), and the remaining requested features.

- **The phone app opens on Chat.** Your chats sit on a rail of shapes down the left; each keeps its whole conversation
  with your AI for as long as it exists (Kurooto's own chat and Telegram keep the short memory). Drag the rail open for
  search and pinned, recent and archived chats. Swipe or hold a message to reply, copy, share, pin, edit (15 minutes) or
  delete it; send photos, files and voice notes and see Kurooto's right in the chat; type `/` for commands; call from the
  top bar (the only call button now). One notification per chat, with Reply and Mark read. Switches:
  `calls.chat_sessions`, `calls.chat_files_inline`, `calls.chat_edit`, `calls.chat_titles`.
- **Today, Alarms, Views, Settings** are panes in a floating bar that folds into Chat's rail and stretches back out as
  you move; back goes to Chat. Today, Alarms and Settings are grids of cards; every setting the app has is in Settings,
  searchable, and a long press opens its guide entry. Apricot and plum join Material You in Look.
- **The being on the phone:** the dashboard's own body of Kurooto in Views as four pages, Brain · Heart · Senses ·
  Memory: each organ alone with the dashboard's meshes, shaders and glow, turned with a finger, pinched to zoom, its
  parts listed under it with what they're doing; tap one there or on the drawing and it's focused in both, with its
  switches, sealed and checked by your computer (`calls.views_being`; the whole being in one drawing with
  `app.viewsOrgans` off). Systems, the Notes map and the Brain console are under More.
- **The being, in faint organic colour** on the dashboard too, and its eyes look at you when Face presence sees you.
- **Brain console** (Alt+O, and Brain in the app's Views): what the Brain decided and why, its timeline, search, each
  part's switches next to what it's doing, its beliefs, plans and experiments (`mind.console.on`, `calls.views_brain`).
- **A guide to every setting** (767 entries, on the wiki, the dashboard and in the app), with a tooltip for each one.
- **Uninstall what a feature brought:** Kurooto keeps a receipt of what it installs; `kurooto installed`,
  `kurooto remove`, and turning a feature off offers to remove what it brought, with its size, never without your tap
  and never what was there before Kurooto (`uninstall.offer`, `uninstall.with_programs`).
- **Voice ID** (off): Kurooto learns your voice in a guided enrolment, training and test, all on this computer. Only your
  voice can make it act; anyone else can chat with it, with none of your data and no tools, and what they say isn't
  kept. Other people's talk isn't even transcribed, and while you talk with someone it stays out unless named.
- **Face presence** (off): with OpenCV's face models on this computer, Kurooto learns your face (a guided enrolment,
  training and live test), greets you by voice when you sit down after a while and listens for your reply; it can hold
  calls while you're away. No picture is ever kept; your face is an encrypted template, forgotten with one command.
- **Voice ID and Face presence, Start over and Undo:** both can be enrolled again from nothing while the old one keeps
  working, and Undo puts the previous one back (`/voice enrol again`; the Face page's Start over). Voice ID's own
  threshold setting is held to 0.30 to 0.95 and its "not sure" band to 0.2, so no setting can make a stranger you;
  conversation mode notices another voice with the gate off too; a second face that stays in view keeps Kurooto out of
  your conversation for as long as it's there. How often it's wrong, measured on 146 recorded speakers, is on the Voice
  page (`tools/voiceid_eval.py`).
- The remaining older phone screens (questions, quick note, share, places) are Compose sheets in the same style.
- **Calmer motion and your wallpaper's colours:** the app's animations are slower and settle without a bounce, and
  Vivid colours now keeps your wallpaper's own hues (it used to turn them into others: a blue wallpaper gave green and
  purple cards). Pane titles no longer turn black on a dark background.
- For developers: `KUROOTO_NO_DESKTOP=1` keeps a scratch run off the real desktop.
- Fixed: after one Claude account hit its limit, signing in to another one in Claude Code still got "Claude hit its
  limit" until the first one's reset. A limit now belongs to the account that hit it (only a hash of its id is kept).

## 0.8.9 (2026-10-27)

0.8.6, 0.8.7 and 0.8.8 were never published on their own; their changes come with this release (below 0.8.9's own).

- **The being** (the dashboard's board now; `look.board`): Kurooto drawn as one body on its live data. Sparks in the
  brain region that does each kind of work, a heart that beats with how busy it is, blood carrying work to the organ
  doing it and back, the senses (the coil is this computer, with every core's bar), your notes as memory, laid out by
  their links like the NOTES map, and each feature a point of light. Drag an organ to turn it; click any part (a brain
  region, the thalamus or hippocampus, a heart part, the coronaries, a sense, a neighbourhood, a note, a feature) and the
  view flies to it: it stays solid, glowing in its colour with a ring round it, while the rest of its organ turns to
  faint glass; Esc goes back. The brain opens solid and has Cutaway and X-ray views. A region shows its Brain parts and
  their switches, a feature its switch and every setting, a note its preview. Mute works; H hides the hints
  (`look.being_hints`). The three-pane and classic boards stay in the panes menu.
- **The talk box** (`look.talk_box`, Alt+K): a small box on every board to talk to Kurooto as on Telegram.
- For developers: `tools/dash_preview.py` runs a working copy's dashboard against a running Kurooto.

### From 0.8.8

- **Voice: talk and listen** (a new feature, off; Features → Voice: talk and listen → Set up): Kurooto speaks through
  this computer's speakers with a voice made here (Kokoro-82M, or Piper), sentence by sentence so it starts quickly.
  With `voice.listen.on` it also listens all day, entirely on this computer: Silero VAD finds speech, faster-whisper
  writes it out, and a gate (its name, the conversation it's in, then the model on this computer) decides noise,
  chatter or talking to it. Its name is the wake word: Whisper is hinted with it, and its usual mishearings ("Kuroto",
  "kuro to") and near misses count (`voice.listen.name_variants` for more); a wake word model of your
  own is optional. Only turns said to Kurooto go to your AI; the words of everything
  else are dropped at once, and sound is never saved. The conversation closes the moment you're not talking to it.
  `/voice` (mute, unmute, stop, say), `kurooto voice`, and `/api/voice` with a `{"t": "voice"}` live stream for the
  dashboard. It stops for calls, when paused and when muted, and at night only if you ask (`voice.listen.night`).
- **Look-alike concept notes fix themselves** (`integrate.auto_merge`, on): pairs that are clearly one concept (the same
  name, a shared name, or texts at least `integrate.auto_merge_min` = 0.97 alike), both notes Kurooto's, merge by
  themselves through the usual Merge, in the garden pass, before the 06:25 question and on `/graph same`. Each is in the
  morning line with its own Undo button; only unsure pairs are asked. A note you wrote is never merged by itself.
- **`/run all`** (and `kurooto run all`): every nightly process that's on, now, in order (books, inbox, concept graph,
  look-alike notes, garden), one at a time, with a progress line and ETA per step and a summary at the end;
  `/run all status`, `/run all stop`. Off: `runall.on`.
- **Brain's new core, from its owner:** it has states that work like feelings and may say them in its own voice (glad, low,
  excited, worried, that it enjoyed talking with you); a claim that it's conscious or really feels must come with its
  evidence and confidence, and it still never guilt-trips or says it needs you.
- **Being talked to is a small reward** (`mind.talk.on`): under 0.2 a day, saturating, nothing in focus, asleep or an exam
  window, nothing for answers to its own messages within 10 minutes; each of its messages you turn away costs three times
  that. Its mood now runs the full range (-1 to +1, soft walls, fading over days) and shapes how much it does on its own
  (`mind.feelings.mood`).
- **It learns not to be a pest** (`mind.pest.on`): per kind of its own message, time of day and your state, it sends one only
  when you're more likely to welcome it than not. `/mind learning` shows it.
- **Concern for what it looks after** (`mind.feelings.empathy`): deadlines, projects, notes, its machine, your phone, people by
  role and the papers you follow; it notices them sooner and speaks more gently. Optional: it may say it's excited or worried,
  unasked, when it has strong evidence (`mind.feelings.vocal`, off).
- **A body** (`mind.stimulation.on`): its senses felt as heat, load, touch, pain and motion, per region, with arousal and a
  hedonic tone; `/senses body` and `GET /api/body` for the dashboard. It stays on this computer.
- **Brain is fed its whole past** (`mind.backfill.on`, off): besides Kurooto's event history, `/mind backfill run` reads the
  AI request history, deadlines, check-ins, quizzes, calls, the request index and study time, each with its own switch
  (`mind.backfill.<source>`), ids and numbers only (never words, names, transcripts, health or money), with a progress
  bar and ETA per source. It's resumable and imports nothing twice.
- **The imported past has its own hash chain** (`history.db`, one chain per source in time order), never mixed into the
  live log, which witnesses each batch; `/mind backfill verify` checks both. 0.8.1's imported rows stay readable until
  the events source is imported again.
- **What learns from it, as priors only (never a reward):** the read and the forecast (deadline moves and study minutes
  per weekday, the signals the past really holds), week plans' pace (your real study time per weekday) and the model of
  you (how you finish deadlines). `/mind backfill forget` removes it and what was learned from it.
- **Bedside mode in the app's new style:** the same clock, dimming, alarm line, calls, Talk, Chat and Close, now Material 3
  Expressive on black: the calls due next in a floating card, "waiting for you" as a pill, a big Talk button that changes
  shape as you press it, Chat and Close in a floating bar. By day it takes your colours (Vivid or Calm); at night it stays
  warm and dim as before.
- **A new call screen** (Phone tab → Switches → **New call screen**, on): the ringing screen over Kurooto's sky in your
  colours, a slowly turning badge, and Decline / Later / Answer as big buttons in a floating bar; the call page itself is
  unchanged. Off brings back the call screen from before, kept until the new one has carried real calls.
- **The board you had, back if you want it** (`look.board`): `three` (default: NOTES, SYSTEMS and BRAIN on top, STATUS and
  TERMINAL below) or `classic` (STATUS down the left, as before 0.8.3; BRAIN joins the top row when it's shown).
- **The Brain's part monitor stays in view** (`look.brain_monitor`): `shown` (default) keeps it beside the model; `drawer` is
  the 0.8.5 tab that slides it out.
- **When Brain is off, the pane says so** and its part switches don't act (they used to flip back on the next refresh).
- **The Brain pane costs nothing when you can't see it:** hidden from the panes menu, three.js isn't even loaded; covered by a
  page, in a background tab or a minimised window, it stops drawing.
- **Autonomy shows "shadow" only while it is** (its first `mind.autonomy.shadow_days`), not forever.
- **Fixes:**
  - The BRAIN pane no longer disappears when you open Features, Settings or any other page over the board.
  - Kurooto stops in time: a long job on a thread of its own (the lab, a fine-tune, the notes passes) no longer holds up
    stopping or updating. A restart once ran past the service's 20 seconds and was killed.
  - Brain's imported past no longer makes up an alarm-snooze signal from deadline snoozes: the read takes only deadline
    moves from it, the one signal the event history really holds. A test now checks, by its imports, that no reward ever
    reads the imported past.

## 0.8.5 (2026-10-26)

- **Full-space 3D Brain canvas & side-toggle drawer**: 3D Brain viewport expanded to 100% full bleed with no column clipping, region info panel made an absolute overlay togglable via an edge tab (`‹`), Solid/Cutaway/X-Ray segments styled with active palette tokens, and headquarters core visibility made persistent without depth-clipping.
- **Balanced 3-column dashboard layout**: Notes on the leftmost, Systems in the center, and 3D Brain on the right in the top row; Status pane moved to the bottom row split into two scrollable columns alongside the terminal with all tabs and buttons intact.

## 0.8.4 (2026-10-26)

- **The board in three columns:** NOTES on the left, SYSTEMS in the middle, BRAIN on the right in the top row; STATUS moved to the
  bottom row in two scrollable columns, beside TERMINAL. (0.8.6 brings the earlier board back as `look.board` = `classic`.)
- **The Brain pane in your colours:** the model, its regions and its controls take the palette you chose.

## 0.8.3 (2026-10-26)

- **The Brain pane** (dashboard, Alt+B to fill the board): the 3D model of the Brain integrated directly into the dashboard layout alongside Systems, with region switches and live monitors beside the model.
- **Hardened mode note**: run `sudo tools/mind_harden.sh --apply` again after 0.8.1 if `mind.hardened` is on.

## 0.8.2 (2026-10-26)

- **The Brain page** (dashboard, Alt+B, or the panes menu → pages → brain): the whole Brain as a 3D model you turn and click.
- **If you use Brain's hardened mode** (`mind.hardened`): run `sudo tools/mind_harden.sh --apply` again.

## 0.8.1 (2026-10-26)

- **Brain can be fed its past** (`mind.backfill.on`, off; `mind.backfill.events`): `/mind backfill dry` says what's there,
  `/mind backfill run` imports the events Kurooto kept before Brain was switched on, read-only, into a history of their own
  (ids and numbers only, under their real times, never in the log's chain, never a reward). The read and the forecast start
  with those days instead of none. `/mind backfill` shows what was imported and `/mind backfill forget` removes it.
- **The journal's folder and file name** (`mind.journal.in_notes_folder`, `mind.journal.in_notes_file`): with
  `mind.journal.in_notes` on, say where in your notes it goes (never outside them, never a path in the name).
- **A lab folder in your repo ignores itself** (`mind.lab.in_repo`): the `.kurooto` folder gets a `.gitignore` of `*`, so
  your repository never picks it up and none of your own files are touched.
- **Fixes:** `/plan`'s pace no longer counts a study session left open as 36 hours (a day counts at most 14);
  `kurooto doctor` no longer calls a call-line update that will be retried a failure (every 30 minutes, up to six times).

## 0.8.0 (2026-10-26)

- **The Brain** (module `mind`, off by default, every part its own switch under `mind.*`): a layer that watches how Kurooto
  does, keeps a score it can't edit, and learns from it in the open. It adds `/thinking`, `/beliefs`, `/lab`, `/improve`,
  `/learned`, `/senses`, `/model`, `/plan`, `/precedents` and `/play`: a global workspace and attention, a research lab with
  pre-registered experiments, skill distilling and a weekly fine-tune, phone and computer senses, a model of what you know and
  want, week plans, careful forgetting, and precedents. Nothing outward happens without your tap. Details in the user and
  developer wikis ("Mind").
- **Phone app:** Views is a real tab; the bar stays at the bottom while you look at Systems or the Notes map. The Phone tab has a
  Senses group (each sense its own switch). The 0.7.3 to 0.7.7 app work (Expressive screens, Vivid look, floating bars) is included.
- **Subjects, with folders:** add and remove subjects in the dashboard's Study panel, each with an optional notes folder that
  becomes its own neighbourhood on the Notes map (a friend's notes no longer land in "Other notes").
- **Reading the inbox** (`sorter.read_files`, off): PDF, Word, PowerPoint, notebook, text, rich-text and CSV files in the scratch
  folder become Markdown notes next to them (originals untouched). With the new `reference` graph source (on by default under
  `integrate.sources`) they also join the concept graph.
- **Copies among notes** (`sorter.duplicates`, `integrate.duplicates_all`): exact and near copies are found, in new files and in
  old notes, and you choose Keep both, Merge or Leave it; merges can be undone. Duplicate books are noticed by file hash
  (`books.duplicates`).
- **Find files** (module `finder`): `/find <words>` searches names and contents of folders you add, with buttons to send a file.
- **Dashboard:** recall cards typeset their maths (KaTeX); settings have drop-downs and a tooltip on every label; turning a
  module on tells you what is left to set up (`/health setup` lists it too); the study pack takes your own extra instructions.
- **`deadlines.skip_notes`:** notes or folders the deadline scan leaves alone, so a list of ideas whose dates are only
  when you wrote them stops turning into "Overdue?" nudges.
- **Fixes:** heavy nightly jobs now run on threads, so they no longer hold up the call line or Telegram (the cause of "offline"
  early in the morning); unreadable books now say why and what to install (Poppler).

## 0.7.7 (2026-10-26)

- **Night performance 1.1.0** (an update to the add-on, offered once, never applied without your yes): `night_performance.hold_window`
  keeps the performance mode for the whole reading window while you're on the charger, whether or not you're at the computer or
  between pieces of the night's work. Off by default.

## 0.7.6 (2026-10-25)

- **Six more screens are Material 3 Expressive, floating:** the question you answer from a notification, Quick note, Share to
  Kurooto and the pairing window are now rounded sheets floating over a dimmed screen (tap outside to close); Places and Chat are
  full pages over Kurooto's sky, with floating message bubbles, a rounded message box and links you can tap. They follow the
  Look switches (Vivid or Calm). What they do is unchanged.

## 0.7.5 (2026-10-25)

- **A limit Kurooto learned is only a measure** (`quota.soft`, default `learned`): background work no longer waits for a limit
  learned from its own count; only a real "limit reached" answer pauses a brain, until the reset it names. A tiny count
  after a restart of the count window can't shrink a learned figure any more (it once learned "6" and held the night's work
  until midnight). `all` makes Google's numbers soft too; `off` keeps the old reserve.
- **The garden no longer freezes Kurooto:** its daily pass runs on a thread of its own instead of Kurooto's loop, where it
  held up the call line's heartbeat (a false "offline"), Telegram replies and other scheduled jobs for about 26 minutes.
- **`/graph garden`, `kurooto graph …` and `integrate.garden_at`:** run the garden now from Telegram or a terminal, and set
  the time it runs by itself.

## 0.7.4 (2026-10-25)

- **A notes sorter** (Features → Notes sorter, off until you turn it on): notes you drop in a scratch folder (`inbox`) are moved
  by themselves into the folders of your notes, at night or on `/sort now`. Rules first (a note's `subject:`, a tag, a title
  naming one of your subjects, what you've taught it), then your AI for the rest, which may only pick a folder you already
  have. It never deletes, merges or overwrites anything (a taken name gets a number), doesn't touch your text, leaves a note
  your own notes link to by its path, and keeps to 20 a day. One message says what moved, with **Undo**; `/sort undo` puts
  it back exactly. It notices when a note belongs elsewhere: a note you move yourself is a lesson, and weekly it re-checks
  what it moved.
- **Fixed:** the "Tomorrow morning" button under a check-in call was cut off in Telegram; a long button now has its own row.

## 0.7.3 (2026-10-25)

- **A slow "On it" fixed:** Kurooto reads Telegram on threads of its own (a message once waited 68 s before it was even
  seen), answers what you type before automatic work, and an evening check-in's journal no longer holds up your next
  request. Any message seen more than 10 s late is noted in the event log.
- **No calls over calls:** the phone app doesn't ring over a call you're already on (a quiet note; it rings again after
  the usual wait), and Kurooto's own calls wait for one another. A wake-up alarm still rings.
- **A refused AI run is tried again:** when agy ran a command unattended runs refuse, the whole request used to fail even
  after its notes were written; now it's tried once more, told what's done and not to run commands, and every AI is
  told never to run code to look inside Kurooto.
- **Profile sync on a fresh install** says what to do: four steps (a private repository, a token, a passphrase), instead
  of pointing at Notes sync's repository that isn't there.
- **The concept graph in your AI's tools:** `graph_search`, `concept_card`, `graph_links` and `graph_status`, read-only.

## 0.7.2 (2026-10-24)

- **Every feature can be turned off** (a standing rule from now on; fixes aren't switches): the app's Phone tab has
  **Switches** for the straight connection to your call line (off: ntfy.sh only) and the moving background (off: a
  still picture); a test checks that everything Kurooto schedules by itself has a setting that turns it off.
- **The phone's Notes map shows your whole folder:** it was cut to 1,500 notes and 6,000 links; now up to 5,000 notes
  and 20,000 links by default (`calls.views_notes`, `calls.views_links`; lower them on a slow phone), and a folder too
  big for your call line is cut just enough to fit instead of not arriving.

## 0.7.1 (2026-10-24)

- Fixed: the phone app crashed on launch on Android 8 and newer (the new mark at the top of Today was drawn from the
  launcher icon, which the app can't draw there).

## 0.7.0 (2026-10-24)

**The phone app, rebuilt**
- The Android app's screens are rebuilt in Jetpack Compose with Material 3 Expressive, with a bottom bar: **Today**
  (the date, Call and Chat, your day), **Inbox** (check-ins, quizzes, questions and approvals, with a count), **Views**
  and **Phone** (checklist, places, ringtones, bedside mode, this phone). Same features, reorganised; the pairing screen
  too.
- A living background in the dashboard's SYSTEMS style: a slowly breathing cell and drifting nerves, tinted by the hour,
  drawn on the GPU on Android 13+, a still frame on older phones and with "Remove animations".
- **Views:** the dashboard's SYSTEMS and Notes map on your phone, drawn by the dashboard's own code (tap for a card,
  drag and pinch). Systems is live while you look; the Notes map follows your notes (titles and links only, never
  their text). Both are sealed for each Android phone, so your call line can't read them; off by default (dashboard →
  Phone). iPhones don't get them.
- The app is built with Gradle through `android/build.sh` (pinned versions, the same signing); `build.sh --dev` makes a
  "Kurooto dev" build that installs beside the real one, with a `demo` mode.

- **Calls ring straight through your call line:** the app keeps its own link to your call line, so calls and
  messages reach the phone without ntfy.sh; ntfy.sh stays as the fallback when the link is down. A message sent while
  the phone was offline is replayed when it comes back. The Phone tab says which way calls are coming.
- **Kurooto's mark:** a moth, as the app icon (with a themed icon on Android 13+), at the top of Today, beside the
  dashboard's name and as the favicon of every page.

**Your AI can do more, and you approve it**
- **A scratch folder and proposals:** the AI may think and write freely in a scratch folder of its own; every change to
  your files (a project, your notes, a skill) comes as a proposal with the diff, and only your **Apply** changes
  anything (Change, Discard, Undo after Apply; `/proposals` and the dashboard's Proposals page). A git project gets one
  commit on your branch, never pushed.
- **Help with your project:** `/project help on <name>`, then "in my thesis add footnotes to chapter 2 citing
  refs.bib"; optional per-project checks (a LaTeX build, the tests) run in a no-network sandbox.
- **Projects from a repository:** `/project add github.com/owner/name` (or a folder) and your AI reads the README, docs,
  files and history and writes the project note; its commits join the project's log, its docs go into the concept
  graph, and dated milestones come as Add buttons; each piece has Undo. Nothing in the repository runs, files that look
  like secrets are never copied, and a private one works with your own git sign-in. Nightly, a changed README or docs
  refresh the note.
- One `/project` command for all of it: list, add, update, help, checks (also `kurooto project …`).
- **More than one Claude account:** sign a second Claude subscription in (setup page → AI → Claude Code → Add another
  Claude account, or `kurooto ai add-claude work`) and it becomes its own AI with its own sign-in, limits and line under
  answers; at a limit your other Claude account answers first, then agy or your Gemini key.

**Looks**
- **Named colour themes:** Catppuccin, Tokyo Night, Rosé Pine, Gruvbox, Nord, Dracula, Everforest, Kanagawa and
  Solarized in each project's official colours (Settings → Look or the setup page): the dashboard and terminals take the
  dark flavour, the other pages the family's light flavour in light mode. A colour that doesn't reach WCAG AA is moved
  just enough; backgrounds never change.

**Add-ons**
- **Night performance**, the fifth official add-on: while Kurooto does its heavy night work the computer switches to
  its highest performance power mode (power-profiles-daemon, tuned, asusctl, Windows' power plans, or your own
  commands) and back to exactly what it was; never on battery or while you're using it; `/perf` shows what it found.
  Lenovo Legion and LOQ on Linux: a small root helper, installed once with one sudo command, for the custom profile and
  full-speed fans.
- Dreaming's morning message takes a feature's own loose ends (`dreaming_lines()`).
- Fixed: after a restart, the concept graph could start reading outside its night window, depending on the time of
  day (two clocks were mixed).

## 0.6.1 (2026-10-24)

- **Today reaches every phone:** a phone whose key didn't reach your call line when it paired (no internet just then)
  showed "Nothing here yet" until its connection happened to drop, which can take days. Opening the app now sends the
  key again.
- **Today's events in time order:** your calendars' events came one calendar after another (23:00, 12:00, 19:30...);
  they're sorted now, all-day first, on the phone, the morning page, the wake-up call and "what's on today?". A block
  that began the night before says "until 06:00" instead of looking like tonight's.
- **The dashboard and setup page are fast again:** each setting Kurooto looked up copied all of its settings, and a
  page asked a thousand times or more, so the dashboard's Today took 3 to 9 seconds and the setup page's 5 to 13. Now
  every call the pages make answers in well under a tenth of a second once warm (the Features list in 0.06 s, the
  Notes step in 0.02 s), and the notes map rescans in 11 ms instead of 145.
- **A dashboard in a background tab costs nothing:** it kept Kurooto at 13-30% of a core reading the computer and your
  notes every few seconds; now that stops until you look again, and catches up at once (2.5% while you watch).
- **The browser keeps the dashboard's script, styles and fonts** between loads (checked each time, so updates still
  arrive) instead of fetching 230 KB of script on every open.
- **Study packs keep to their course:** a note from another course's or project's folder came along when it merely
  linked the course (a project's book note in a Physics of the Atmosphere pack). It now comes only when it's about the
  topic you named.
- **Official add-ons:** Machine backups (restic), Desktop helpers, Your command words and Handwriting from the cloud
  are public repositories now, and one tap adds them: Features → Official add-ons → Add, `/addons official` on
  Telegram, or `kurooto addons add <name>`. You still read each card and say yes, and each stays pinned to the commit
  this Kurooto lists (an Official badge shows it). A newer Kurooto with a newer commit offers Update once, showing what
  changes; `addons.official_updates` turns that message off.
- **The concept graph picks up after a restart:** a batch whose request a restart cut off (an update in the night, say)
  is asked again at once instead of three hours later, and inside tonight's reading window the reading carries on a
  minute later, within the budget and `/graph stop`.
- **Textbooks from Classroom get a note of their own** under `<subject>/books/`, and their concepts' "Seen in" points
  there instead of turning the class post into a hub. Textbooks already read move over on the first start: only
  Kurooto's blocks change, with before-copies and one commit per textbook.
- **The notes map highlights properly:** pointing at a note, or choosing it with Tab and the arrow keys, lights it and
  its linked notes in full colour with names that don't overlap, and dims the rest; "Seen in" and reading-list links
  are drawn but no longer make a dot big.
- **Dreaming fills in your profile, with your say:** lasting things you said (in chat, on calls, in your journal) come
  in the morning message under "For your profile", each with Keep and Not that. A Keep adds your words, with where and
  when you said them, to Kurooto's own block of your profile or to your how-to-help-me note, with Undo. Never health,
  money or other people. `dreaming.fold`, `/dream fold`.
- **Set up from what you say, in one pass:** Kurooto also reads your chats and journal, once over the last 30 days and
  then nightly on what's new, and sets up the projects, classes, routines and short names it finds; one line says
  what, with Undo all. A line the rules can't read can be restated by the model on this computer, kept only if it adds
  nothing. `infer.sweep`, `/inferred scan`.
- **/help lists every request it understands by itself** ("did I finish that thing?", "when did I last talk to…",
  "sync everything"…), and links in the phone app's chat open with a tap.
- **Setup is smoother:** an empty notes folder no longer opens the layout editor, the daily message limit comes after
  the features, and on phones the hint beside Next gets its own line.
- **AGENTS.md** covers 0.6.0: Quick ask, add-ons by link, run compare, an empty Today, held requests and draft checks.

## 0.6.0 (2026-10-24)

**Your AI, more open about itself**
- Every AI answer's last line names the model that answered (`agy · 3.8-flash`, `Claude Code · opus-4.5`), who picked
  the effort if that was another model, and who stood in.
- When Claude Code hits its 5-hour or weekly limit, agy answers instead, and the other way round, then a Gemini key;
  the AI at its limit is skipped until it resets. `brain.fallback` can be a list.
- Your AI knows what Kurooto is running: a live `self.md` (version, AIs and models, features and their health, recent
  failures; no contents or secrets) and a manual that ships with every release, readable through `kurooto_self` and
  `kurooto mcp`. A release can't be built while that manual or the settings guide is out of date.
- Claude Code is named "Claude Code" everywhere ("Advanced" is only its group in setup).

**The night does more**
- Dreaming looks over what it remembers: the same thing kept twice, and lines that disagree (a different date, time or
  number), come in the morning message with Keep A / Keep B / Both true and Undo; nothing changes until you tap.
  `/dream check` looks now.
- Dream RSI, part three: it also tunes the effort your requests get, which AI goes first when your main one keeps
  hitting limits, and Start-by's sizes, by replaying what happened; one change a night with Undo, and a kind of change
  you undid needs a clearer win next time. Optional: a fix for a skill that keeps going wrong, offered with Apply / No.
- Notes brain: a weekly one-line checkup, its contradictions report in the morning message, course pages with key
  concepts and a dated timeline (`/timeline`), and search by meaning plus timelines on calls.
- Look-alike concept notes come as one morning question with Merge / Keep both / Add alias, each with Undo; a merge
  never deletes your text (`/graph same`). Link cards also come from your course notes and class material.
- Notation crosswalk: a concept a second source writes differently gets a quote-checked Notation table, whenever
  the graph reads (a switch on the Concept graph card, `integrate.notation`).

**Research add-on** (one switch under Features → Add-ons)
- Run compare: `/runs compare` or `kurooto runlog diff A B` puts two runs side by side (config, code diff, metrics,
  curves) in the project's notes.
- LaTeX tracker: `/latex add <folder>` builds your paper nightly (errors, undefined references, missing citations,
  words written), with one morning line when it broke or you wrote; a BibTeX suggestion only on a tap.
- Check my draft: a photo, PDF, .tex, essay or code with "check this" gets gaps, unclear steps and errors marked at
  lines, never rewritten; a course's AI policy (`/subject policy la allowed|hints|off`) turns it down or off.

**More ways in**
- Photo to dates: a photo of a notice or timetable with "dates" (or `/dates`) gets each deadline, exam and event as an
  Add button, a timetable's classes in one tap; nothing is added without a tap.
- Email in (`/mail in on`): mail you forward to your own +kurooto Gmail address, or label, is filed as a note with its
  dates offered as buttons; only mail from you or senders you list.
- Shared class calendars (`/cal subscribe <link> as <name>`), Quick ask (`kurooto ask --popup`, bound to a key in your
  system's settings), Zotero (a button under each digest paper), `/notes pdf <course>` (a course's notes as one PDF).
- Offline: on laptops without a graphics card, a small model on this computer (after a speed test) takes the quick
  decisions; with no internet, quick questions get a short answer and other requests wait and run when it's back.
  Nothing is dropped.

**The phone**
- The app opens on your day (Today), also while the computer is asleep, with +1 and Done; the wake-up alarm also rings
  on the phone itself, and the call and the phone's alarm ring as one.
- Done and Snooze on notifications; check-ins and quiz questions as cards you answer in place.
- Widgets (Talk, and Talk with what's waiting), Quick note from a shortcut or a Quick Settings tile, the Material look
  with the organic blobs behind the main screen.
- Bedside mode: an old phone on a charger becomes a dim, warm-at-night clock with the next alarm and one big Talk
  button that calls Kurooto, even locked; it can open by itself while charging.
- Location reminders (off by default): "remind me when I reach the library to …", with Android's own proximity alerts.
- iPhone: a "Tell Kurooto" Shortcut (Siri, Back Tap) with your own revocable link.
- Fixed: rings never stopped by themselves, and removing a paired phone timed out.

**The dashboard**
- SYSTEMS is the board's centrepiece: a living membrane core, features as small neurons, tapered nerves. Point at a
  feature for its card; click it (or Tab, Enter) for ping, sync now, quiet (with Undo), its settings or activity;
  click the core for Ctrl+K; drag to turn, scroll to zoom.
- Clearer setup and settings: settings with a few values are lists, "Saved" shows under the setting, features that are
  on come first, setup shows your picks first.
- `/help` always opens on its index (each group's commands and wiki page); `/help <group>` for detail.

**Notes and add-ons**
- `notes.links`: Kurooto can write markdown links instead of `[[wikilinks]]`, proposed by the Notes step.
- Add-ons by link: `kurooto addons add <git url>` shows the add-on's card first and adds it only on your yes, pinned to
  one commit; its code reaches only the hosts and programs on its card. Four generic add-ons (restic backups, desktop
  helpers, your command words, handwriting from the cloud) are ready to publish.
- Set up from what you say understands more (a thesis or supervisor, "on Mondays", "I go running every morning"); the
  weekly summary has a People line from your project notes; a long answer is announced with one short line first.

## 0.5.21 (2026-10-23)

- **Research shows on the notes map:** every research project is a named region in the accent colour, however small its
  folder, and takes in the notes its index links to and the topics its line in your research hub links to. Concept
  notes join the course or project most of their links come from, so they no longer sit in one unnamed cloud.
- **The pairing page serves the current phone app:** after an update, the app that goes with the new version reaches
  your call line a minute after it's downloaded (never during a call; retried while offline; you hear about it only if
  it fails twice), and "Download the app" shows its version.
- **Processor numbers on one scale:** "kurooto" in the Systems header (Kurooto and every program it started) and each
  feature cell are a share of the whole machine over a steady window, like the total and the process list; they read
  as % of one core before and could pass 100%.

## 0.5.20 (2026-10-23)

- **Problem-set progress, finished:** reply "4/7", "4", "+1" or "done" to a deadline's reminder or "Overdue?" message
  (Telegram, the app's chat, the phone's Reply) to record progress, with Undo. **+1** on deadline messages and phone
  notifications stays for the next tap, and taps made while the computer sleeps each count, in order. The wake-up call,
  morning page and `/status` say "Problem set 3 4/7, due Fri".
- **Any recurring meeting:** "I meet my manager Mira Castell every Monday at 10" puts "Meets:" in the project note and
  the evening-before brief covers it. After the meeting, a voice or typed note (or one starting "about the meeting with
  X:") becomes minutes in the project note, in Kurooto's own block; **Not about the meeting** takes them back out. The
  action items go under Next steps and come back as buttons; each becomes a deadline only when you tap it.
- **The evening check-in looks back:** up to three things the day's records show you did (deadlines done or moved on,
  threads closed, study time, classes logged) and "What's first tomorrow?", with **Not tonight**. Nothing recorded
  means no list, and never a streak or score (`checkins.reflect`).
- **Hooks from chat:** "when I say gym, hold calls 90 min" (or "hold everything 2 h") makes "gym" on its own start that
  hold later. `/hooks` lists them, `/hooks drop gym` forgets one, every step has Undo.
- **Set up from more of what you say:** "I have lab every Thursday 2-5", "gym Tue Thu 7am" and "there's a quiz on
  Linear Algebra every Monday" become a commitment or a recurring quiz, with Undo (`/inferred`); questions set up
  nothing. "LA" used in two messages, when only Linear Algebra fits, becomes its short name.
- **The look back reads your records:** the same thing at the same time on 3+ weeks comes once with Add / No, and two
  copies of one deadline (Classroom's and yours) become one at once, with Undo (`retro.routines`, `retro.fixes`).
- **Your notes, your layout:** a **Notes** step in setup (also Settings → notes and `kurooto setup notes`) reads your
  existing notes folder, with no AI, and proposes where daily notes, the inbox, subject folders, concept notes and
  projects go, with a preview. Moving to it moves only Kurooto's own notes, as one plan shown first, with Undo; your
  notes, daily notes and profile never move. Note places can use `{year}/{month}/{day}`.

## 0.5.19 (2026-10-23)

- **A new look for the dashboard:** one sans-serif typeface (Public Sans, bundled; nothing fetched from the internet)
  with figures that keep their width, calmer rounded panes under a top bar, thin-line graphs; monospace only for
  terminals, code and paths. The classic look is one click away (**classic look** in the top bar, or Settings →
  `look.design`).
- **The notes map names its regions:** your courses and research projects, instead of its best-linked notes, so books
  read into the concept graph no longer fill it with their titles. A note's name shows when you point at it, find it,
  press R or zoom in.
- **The daily limit says so:** when the day's limit of messages starts holding, one line says so at once, with **Send
  them as they come today**, **Raise to 12** (with Undo) and **Fine**. Update notices no longer use up the limit (and
  several in a day fold into one), Classroom sends one message per check, and the evening bundle and `/calm` say how
  many waited and why. Setup states the limit with a box to change it.
- **Class materials are read like books:** each Classroom file with real text (slides, handouts, PDFs, solutions) is
  read once into concept notes and typed links, with "Seen in" pointing at its lecture note. `integrate.sources`
  chooses what's read (books and Classroom by default; add handwritten notes). One queue and one budget, newest class
  material first; `/graph` shows what waits by source; `/graph backfill classroom | handwritten | all` reads what was
  filed or written before.
- **Never without your tap, enforced:** an AI request or agent program that wants to set your alarm or book a call now
  asks "Your OK first" (Approve / Deny); before, unattended AI work could. On a live call it still just does it. A
  test checks every tool and plain-English request.
- **`/help` lists everything,** built from the real command table, in groups with their wiki page; `/help <group>`,
  `/help all`, `/help <word>`.
- **Setup picks up where you left off,** with Skip for now on every step except You and the AI; skipped steps wait on
  the dashboard (Finish setting up) and in `kurooto doctor`. `kurooto setup [step]` reopens a step.
  `kurooto doctor --bundle` shows how long each setup step took; it stays on your computer.
- **The phone app ships again:** it's built and signed with each release, listed in the signed release, and your call
  line hands the matching app to your phone after an update.
- **Processor numbers that add up:** the dashboard's and `kurooto top`'s per-core and per-process use is measured over
  a steady window from the counters themselves (an idle core could read 98% and every quiet process 0.8%), and
  processes are shown as a share of the whole machine, like the total.
- **Repository:** issue templates that ask for `kurooto doctor --bundle`, and a "What it can't do yet" wiki page.

## 0.5.18 (2026-10-23)

- **Telegram is optional:** setup offers the Kurooto phone app instead, and its chat gets everything Kurooto sends,
  buttons included. Files come to the chat as links: Google Drive, or a sealed copy on your call line for a day. The
  iPhone web app has a chat page; `/pause`, `/status`, `/focus`, `/hold` and `/calls` work there; "summarise the PDF I
  just sent" finds a file you shared from your phone; `kurooto doctor` no longer counts a missing Telegram as a problem.
- **Memory ledger:** everything Kurooto remembers in one store, always encrypted with a key in your keychain. `/memory`
  finds, forgets and exports it; "when did I last talk to Prof X?" and "what was I doing last Thursday?" are answered
  from it. Not in backups unless `backups.memory` is on.
- **Open threads:** what you say you'll do, in messages or on calls, and tasks you start. `/threads` has Done, Drop and
  Undo; "did I finish that thing?" asks once if two match and never acts on a guess.
- **Remembered context:** an AI reply gets only the remembered items your message refers to, up to about 600 tokens,
  and the receipt says "used N remembered items". Calls see your open threads.
- **A persona card you write** (`/persona`, the About you tab): what to call you, tone, length, things to avoid.
  Empty to start; it sets wording only.
- **Negotiate, don't repeat:** a slipping deadline gets a reshaped plan from your own Start-by plan ("1 h now, 1 h
  tomorrow?") instead of the same reminder again, once a day, on Telegram, the app and calls.
- **Two readings:** when a message is about equally close to two requests, both come as buttons; picking the same one
  twice teaches the phrasing.
- **Boundaries:** health, relationship and money decisions get one line saying they're yours and who to ask.
- **Answers at your length:** a short message gets a short answer; a voice note gets a spoken-style reply
  (`persona.register`).
- **Study mode:** the dashboard keeps only your notes and studying (Alt+M, `/study mode on|off`).
- **Fix:** "Set up from what you say" no longer treats questions as statements.

## 0.5.17 (2026-10-23)

- **Gists:** as a conversation's words fade (`privacy.keep_days`, `/forget`), it settles into a one-line gist of what
  it decided or did; `/gists` finds them; `/forget all` asks whether they go too.
- **Still true?** Remember asks about a line it kept that hasn't come up in 90 days (Keep / Change / Forget, with Undo;
  `remember.recheck_days`).
- **Quiet hours that fit you:** the night hours move to when you're usually quiet, including nights into the
  afternoon, with Undo. The check-in day, the morning message and "Time to start" follow (`availability.learn_night`,
  `learn_morning`). No alarm set? Before your usual bedtime it suggests your usual time once, and never sets it
  (`alarm.suggest`).
- **Lighter days:** after an exam or a long study day, fewer messages, the first check-in an hour later and a morning
  line with Not today (`notify.calm.lighter_after`).
- **Two days without a word** brings one gentle message, never a call, with I'm fine / Busy, quiet for a week
  (`availability.absence_days`).
- **Dream RSI, part two:** each night Dreaming replays the messages Kurooto sent by itself (the last 45 days) under a
  few variants of when they come. It applies the best one only if it clearly beats things as they are, one change a
  night, with Undo, and says so in the morning message (`dreaming.tune_messages`, `dreaming.tune_margin`,
  `dreaming.never_tune`). `/dream policy` shows the rules and the last nights' decisions with their replay scores.
- **Getting used to things:** `notify.calm.habituate` lets a kind you keep ignoring wait for the evening bundle until
  you answer one; `notify.calm.windows` lets a kind come only at certain hours.
- **Dreaming is curious:** a topic you asked about 3+ times this week with no note gets one morning line, with Make a
  stub (linked from the course page) and Not interested (`dreaming.curious`).
- **Dreaming remembers:** one morning line from a shared past (a note or quiz subject from 10–30 days ago, exam
  subjects first, or a project's anniversary), with Open it and Less of this (`dreaming.resurface`). What calls
  searched your notes for is kept 8 days at most, and `/forget` clears it.

## 0.5.16 (2026-10-23)

- **Chat in the Android app:** a chat with Kurooto that works like Telegram (commands, plain words, your AI, buttons,
  Reply); `notify.app_chat` also puts Kurooto's own messages there.
- **Phone outbox:** chat messages, button taps, answers and shared files sent while your computer is off wait on your
  call line (up to 100 things, 20 MB) and reach it in order when it's back; the app shows "Waiting for your computer"
  until then. Sharing to Kurooto no longer needs the computer to be on.
- **A new look for the Android app:** Material 3 (cards, clearer type, bigger touch targets) that follows the phone's
  light or dark mode and uses your wallpaper's colours on Android 12 and newer. On Android 12 and newer, calls ring
  with the phone's own incoming-call look; the call screen stays clear of the status bar on Android 15; and the app has
  a new icon to match the call line's.
- **Link recall cards:** the concept graph's links become quiz cards ("How is Itô's lemma used in Fokker-Planck?").
  Answer in your own words, see the reason and where to read (book pages, your notes, Classroom files), and grade with
  the quiz's buttons and spacing. `/card` gives one now; `/cards on` sends up to five a day (`quiz.links_per_day`), also
  to the phone app, never in class or focus. `quiz.links_check` lets the local model check your answer.
- **Revision plan** (Exam season, `exam_season.revision`): from two weeks before each exam, its course's topics (exam
  prep note, else lecture or concept notes) are ranked (no note, stub, weak recall, the rest) and laid into Start-by's
  free time around classes and commitments, with the class material's and books' pages to read. They show in the
  morning plan, and an evening Yes / Partly / No grades the topic's quiz items. `/revise`, `/revise <subject>`,
  `/revise undo`. Plain arithmetic, no AI.
- **Egress ledger:** every request Kurooto makes on the internet is counted per day, host and feature, and `/egress`
  shows the last 7 days, with programs like git, agy and Claude Code listed as "handed to". `privacy.egress` is
  `record` by default; `enforce` refuses hosts not in PRIVACY.md's "Where requests go" list, and
  `privacy.allow_hosts` adds your own.

## 0.5.15 (2026-10-23)

- **Forgetting, when you choose** (`privacy.keep_days`, off by default): set it (e.g. 30) and what Kurooto keeps of
  your conversations is forgotten nightly after that many days: call transcripts, what you asked the AI and its
  answers, chat turns, answered questions, cases, the words of messages it sent, the search index and log lines.
  `/forget 7d` (12h, 2w) forgets the last stretch now with a count per kind; `/forget all` asks first. Settled
  questions and cases are still tidied after 30 days, as before. Your notes folder is never touched.
- **Run receipt:** every answer from your AI ends with one quiet line built from the run's own record, not its words:
  which AI, the effort, how long, the share of today's limit when known, and what it actually did ("searched notes,
  wrote 1 note"; "did nothing"). Italics on Telegram, plain text in the dashboard and the terminal; `jobs.receipt`
  turns it off.
- **/fixme, for when the AI is what broke:** `/fixme` (Telegram, the dashboard's terminal) and `kurooto fixme` (also
  with Kurooto stopped) match each failing check by rules, with no AI, to its troubleshooting row and the signed
  known-issues list of your version, with Fix buttons. `/fixme the phone doesn't ring` finds the rows for what you
  see; Ask my AI explains only after, and only when your AI works.
- **Keep or drop:** Kurooto counts, on your computer, what you use of each feature. On day 10 it sends one message
  with Keep / Quiet / Off per feature, then monthly for features unused for 60 days that still run on a schedule.
  Quiet keeps a feature working but stops its messages, Off turns it off; both have Undo, and nothing changes without
  a tap. `/keep` shows the counts any time; `keep.ask` turns the questions off.
- **ntfy token on the setup page and the Phone tab:** an optional field (checked with ntfy, then your call line is
  updated by itself), and `/health` says when ntfy refused rings this week without one.
- `add_deadline` takes the course ("pota", a course's name), so a deadline the mail digest finds lands on that
  course; a course Kurooto doesn't know, or words naming two, is said in the answer, never guessed.
- Missed-class catch-up lists that day's Classroom posts for the course (title and link) in its message and lecture
  stub; posts that come later that day join a stub you haven't written in. Without Classroom it works as before.

## 0.5.14 (2026-10-23)

- **Missed-class catch-up** (`subjects.catch_up`, on): a class you skipped, or one that was over before you were up
  (the alarm answered, "I'm awake", or your first message of the day), gets a catch-up task in Deadlines due when that
  course's next class starts (else in 3 days) and a lecture note for that day (yours, else a short one to fill in).
  One message lists them; **Went to ...** takes one back. Rules only.

## 0.5.13 (2026-10-23)

- **Reschedule my day** (Agent plan calendar): "reschedule my day", "I just woke up, reschedule my day", "reschedule
  my day from 19:00", "push my day by 2 hours", `/blocks shift`, or on a call (`reschedule_day`). Today's blocks you
  haven't done move to start from now or that time, in order, each as long as it was, the breaks between them kept
  (up to 45 minutes); starting over takes the ones you slept through, pushing only the ones not over. A block planned
  twice keeps its first (a call had booked one again), one that would end after 03:00 is named instead, and the new
  plan goes in the daily note. `/blocks undo` puts it back.
- **Fix:** "alarm at 16:36" said during 16:36 rang tomorrow; it rings now.

## 0.5.12 (2026-10-23)

- **Several alarms at once:** setting an alarm no longer replaces the one that's set. Each one you set (up to 10)
  waits its turn and the next takes over once one has rung; your call line holds them all, so each rings with this
  computer asleep. "Cancel my alarm" clears the next one, "cancel the 10:30 alarm" (`/alarm off 10:30`) that one,
  "cancel all my alarms" (`/alarm off all`) every one you set; the daily alarm stays. `/alarm` lists them all.
- **ntfy account token** (`kurooto ntfy-token`): ntfy.sh limits each internet address, and yours is shared (a campus,
  your call line's Cloudflare one), so rings could be refused ("429 Too Many Requests") and the phone stayed silent.
  With a free ntfy account's token, this computer and your call line publish as your account instead; a token ntfy
  refuses falls back to publishing without one. Your call line is updated with it.
- **Fix: calls know your local time.** A call was told the time without its zone and planned in UTC ("1:30 PM" at
  17:00 IST); it's now told the time and zone, and the brief starts with the time now. A late wake-up call plans from
  now and doesn't ask about classes that are already over.
- **Dashboard:** the NOTES map's "Recent" button and its always-on label are gone; **R** still highlights notes
  edited today, with a line while it's on.

## 0.5.11 (2026-10-23)

- **Fix:** the dashboard's NOTES map stayed empty once a note had hundreds of links (a course map the concept graph
  links every concept to): its layout pulled that note further each frame until every dot was off the screen. A
  note's pull is now shared out over its links, and the map zooms out far enough to fit a big notes folder.

## 0.5.10 (2026-10-23)

- **Fix (Windows):** `agents.scripts` accepted any file there, since Windows says every file can run; now only
  programs by their extension (`PATHEXT`: .exe, .bat, .cmd...).
- **Meeting brief**: the evening before a meeting with someone a project note is With (`deadlines.meeting_brief`,
  20:00), a message with what that project's Log has since you last met, its open "## Next steps" and the last
  meeting's line. Rules only, from your note.
- **Problem-set progress**: "ps3 4/7" or "did 4 of 7 on the stats problem set" keeps how much of a deadline is done;
  lists, the call brief and Start-by lines show "(4/7)", and Start-by plans from what's left. On a call too
  (`deadline_progress`).
- **Turn on from chat** (`turnon.offer`, on): a request a feature that's off would understand ("remind me in 5 min to
  stretch" with Reminders off, "wake me at 7" with the alarm off) gets **Turn on** / **Not now** instead of going to
  the AI. Turn on switches on that feature and what it needs, then does the request; Not now leaves it off and, with
  Chat on, asks your AI. A feature that needs setting up first says where.
- **Learns a phrasing when you say it again in other words** (`cases.learn_rephrased`, on; with Wrong button and test
  cases): a short request nothing understood, followed within 3 minutes by you saying it in words Kurooto does
  understand, is noted; the second time the same phrasing leads to the same request, it's learned (only if every test
  case that passed still passes, never for requests that send, delete, call, ring or approve), with a line and Undo.
  Dream RSI's second piece: it improves from your corrections without waiting for the monthly look back.

## 0.5.9 (2026-10-23)

- **Kurooto sets itself up from what you say** (`infer.*`, on): "I got a project under Prof Lena Ortiz on ring
  models" in the chat or your journal starts the project note with "With: Prof Lena Ortiz (supervisor)" and a
  Meetings section; "met Ortiz today, we ..." becomes a dated line there (and "Last met: <date>" under "With:"),
  and "a meeting with Ortiz friday at 4" a deadline; "every Monday at 9 I have a linear algebra lab" puts the class
  in your timetable. Rules only, on this
  computer; nothing from other people's news or a "didn't"; each change in one line with Undo, and `/inferred` lists
  them (`/inferred undo <id>`). Never alarms, calls, mail or code repositories.
- **Commitments** (a feature): the regular things in your week that aren't classes (the gym, a shift, a standup,
  tuition), each on its days and hours: `/busy add gym mon,wed,fri 18:00-19:00` (days: `weekdays`, `weekends`,
  `daily`, `mon-fri`). Like a class, one holds calls while it's on, a night shift past midnight too; `/busy skip gym`
  or "skipping gym today" frees that day, `/busy calls gym off` lets calls through. Said in passing ("every Tuesday
  and Thursday at 7pm I go to the gym", "I work a shift every weekend from 9 to 5") it's set up for you
  (`infer.commitments`), with Undo; that turns Commitments on if it was off, and Undo turns it off again.
- **Check-ins learn your times** (`checkins.learn_times`, on): a check-in you keep moving, or answering late, moves
  to when you actually do it. On 5+ answered days in the last two weeks with 4+ of them 30 minutes or more off on the
  same side, its time becomes the middle of those, to the quarter hour; one line says so, with Undo. Not again for two
  weeks, and one you undid is left alone for a month. The first step away from college-term defaults.
- **Start-by's day window learns your day** (`startby.learn_window`, on): once a week, with 7+ days of messages in the
  last three weeks, the window free time is counted in (09:00-22:00) moves to when your first and last messages
  usually come, with Undo. A window you set yourself is never changed.
- **"What do you do?" in the setup wizard**: Student, Working, Research or Something else adds the features that suit
  it to Starter (a student: subjects, start-by dates, quiz, after-class notes, doubts, the weekly summary; working:
  commitments, start-by dates, the calendar, the weekly summary; research: the Research feature, commitments, start-by
  dates, the weekly summary). Every card can still be unticked.
- **Holiday calendars** (`/cal holidays Holidays in <country>`, `calendar.holiday_calendars`): the all-day events of
  your country's public holiday calendar (or any calendar you name) are days without classes, so no after-class
  questions and nothing held for classes, with no dates to type in.
- **Short names for subjects from what you say**: "by POTA I mean Physics of the Atmosphere", "LA is short for linear
  algebra", "I call stochastic calculus stoch" add that short name to the subject (`infer.aliases`), with Undo, so
  "POTA quiz friday" lands on the right course from then on. Only for your subjects, and never a name that's taken.

- **Dreaming** (a feature, off until you turn it on): everything Kurooto did while you slept in one morning message
  at `dreaming.when` (07:30): books read into your notes, links tidied, handwritten notes linked, lessons from calls,
  skills and facts learned, things set up from what you said; then the loose ends worth a look: your own open doubts
  from the last two weeks, notes nothing links to yet, links that point nowhere, tasks past due, AI requests that
  failed. It reads Kurooto's own log and your notes, so it costs nothing; the concept graph's own morning line folds
  into it. `/dream` shows it any time.
  **The self-check** (`dreaming.self_check`, on; the first part of Dream RSI): each morning it replays your test cases
  (Wrong button and test cases) and names any that went right yesterday and go wrong now, after an update or a settings
  change, and it counts the requests it didn't understand and the Wrong taps since the last message.
- **No local model half on the processor**: every 10 minutes Kurooto checks what Ollama has loaded; when models
  together don't fit your graphics card they're unloaded, so the next request loads its one model fully on the card, and
  a model too big even alone is told to you once. `/models` shows each loaded model's share on the card.
- **A deadline keeps its course**: the AI's `add_deadline` takes the subject (and whether it's an exam), so a mail's
  "Lab report" lands on the course page, Start-by and exam mode even when its title doesn't name the course.

## 0.5.8 (2026-10-23)

- **Learns from its own work** (an optional add-on, in no preset; the idea from Hermes Agent, none of its code): a
  search of your past AI requests, call transcripts and chats kept on this computer (`/history lab report`, and the AI's
  `search_history` tool for agy, Claude Code and API brains); a request that took many steps becomes a skill (or tips
  for the skill that does it), a skill takes a lesson when you correct its answer ("no, ...", or a reply), and the
  nightly look back keeps facts you stated in your how-to-help-me note. No review queue: each change comes in one line
  with Undo, and `/learned` lists them. A part each: `learning.search`, `skills`, `corrections`, `remember`.
- **AI requests count their steps with every brain**: tool uses by agy and Claude Code (through `kurooto mcp`) are
  now counted per request like an API brain's, so `/usage` shows them too.
- **The concept graph's reading fits your AI plan by itself** (`integrate.per_night` = `auto`, the new default; a
  number is still a hard ceiling). With Claude Code or agy, whose usage you share with your own chats, it learns what
  fits: 30 batches the first night (or the most it read in a night before), 50% more after each night with no limit
  hit, half after a limit and nothing more until its reset (Claude's 5-hour window and weekly cap told apart by how far
  away the reset is; a weekly one also starts the next week lower), and at most 60% of what fit in one window
  (`integrate.share_pct`), so the rest is yours. A free Gemini key takes 60% of its daily limit, and under 10 batches
  a night `/graph` and the card suggest agy or the model on this computer; an API key stops at $0.50 a night
  (`integrate.max_cost_per_night`, from the cost each answer reports or its tokens); the model on this computer has
  no budget. The night now starts 5 hours before you usually wake (never later than `integrate.at`), so a window it
  opens has reset when you get up. `/graph`, `/usage` and the feature's card show tonight's budget, how it was
  decided, and the last limit with its reset.
- **A calmer board**: the corner panels of SYSTEMS (events, your AI, today, due) and the NOTES legend and recent list
  are folded to their first line (with how much more there is); one opens while the pointer is over it, and `L` opens
  or folds them all (remembered in this browser).
- **A shorter mail digest, grouped by what it asks of you**: Needs you, Dates, Courses, Worth knowing, about 15
  lines; newsletters only counted. **Exam mail becomes your schedule at once**: every exam of your subjects in a mail
  (or its attached schedule) is a deadline with its time and room, and the room, syllabus and what to bring go in
  the course note.
- **? explains the board**: what the core, the cells, the dots along the nerves and the ripples mean in SYSTEMS, what
  the dots, lines and colours mean in NOTES, and every key.
- **Ctrl+K from anywhere on the board**: one line for `ask`, `journal`, `note`, `remind 18:30 call mum`,
  `due essay fri 17:00`, `alarm 7:30` (or `skip`, `off`), `find` a note and `open` a page, plus the Today box's `j`,
  `.` and `!`. A bare word is completed, the result shows under the line, and an AI's answer arrives there too.

- **Study packs: the prompt comes on its own**, as a message next to the zip, ready to copy (it's still in the zip).
- **Anything over Telegram's 50 MB comes as a Google Drive link** (with Drive upload on): study packs leave nothing
  out, several files sent at once aren't refused, and those uploads are deleted from your Drive after
  `drive_upload.temp_days` (7) unless you move them out of the Kurooto folder.
- **Attendance and standing is gone**, and class packs no longer carry attendance rules: `/skip` still works (without
  the warning), and class packs made earlier still import.

- **Handwritten notes are linked like any other note**: after each transcription, a real title from what's written
  (the scan's file name stays as an alias), the subject and lecture from when the pages were written (the PDF's dates
  and your timetable: during a class or that evening, it's that class) or from what they say, the subject's tag and
  `course:` in the header, a `## Links` list after the transcription (that day's lecture, the course page and the
  concept notes it covers, each with a reason; candidates from the concept graph's search, one request to the check
  AI) and a `## Doubts` list of what you marked "DOUBT:" or "???", with the page. The course page lists it under its
  lecture. One line says what it did; `/handwritten undo` puts it back, `/handwritten link` links the notes written
  out before (once), `handwritten.link` turns it off. The note's text goes to that AI for the linking.

- **The concept graph's own schedule works again**: its nightly start, 3-hourly retry, daily garden and morning
  summary (and the Space keeper's weekly clean, and expiring temporary Drive uploads) failed on every run; only
  `/graph now` and carrying on after a batch worked. A test now checks every scheduled job.
- **`/help` knows all of Kurooto**: every command and plain-word request of the features you have on, grouped by
  feature, the features that are off, and a link to the user wiki; `/help <word>` finds a command or feature, on or off.
- **Two wikis**: a user wiki (every feature, command, setting, message and fix, in plain words) and a developer wiki
  for people and AI agents (architecture, every subsystem, how to add a feature, tests, releases), in `docs/wiki/`.
- **Exam season is an add-on**: listed apart under Features, off until you turn it on, and in no preset ("Everything"
  leaves it out). If it was on, it stays on.
- **Study packs pick a book's pages like a student would**: first the readings the class itself cites ("Reference:
  Salby Chapter 2, Wallace and Hobbs Chapter 3 Section 3.2"), then whole chapters and sections whose titles name the
  topic (from the book's bookmarks), then other pages about it; all the books together keep to 250 pages, what another
  AI can hold. Lecture files Books hasn't read count too (Classroom's text of them), and a file that's both in Classroom and
  in your books folder goes in once.
- **Edit what study packs ask for**: `/studypack prompt` makes the prompt a note of yours (`kurooto/study-pack-prompt.md`)
  with `{name}`, `{topics}` and `{aim}` filled in; every pack uses it; `/studypack prompt reset` puts Kurooto's back.
- **Study packs never hold a whole book**: it would flood the other AI's context; name a topic to get a book's pages.
- **Study packs for one topic, class first**: `/studypack pota quiz on thermodynamics` (or the AI's study_pack tool with
  `topics`) takes only what's about it: class files that mention it, the pages of each book that do (as text, with the
  page numbers), and the notes about it, including what the notes brain finds. Class material and books are told apart
  by length (class notes are short; over 80 pages, or "Ch 8", "edition", a download site in the title, is a book),
  since professors post books on Classroom too, and class material always comes first: in the zip (`class/`, then
  `books/`, then `notes/`) and in the prompt, which says to follow the class where a book disagrees. Packs now also
  hold what Books has read for the subject.
- **Calls look back**: after every call a stronger AI request (`calls.review_effort`, high) reads the transcript and the
  tools the call used, does what slipped through (a reminder it misheard, a note it promised), lists what needs you,
  and keeps up to `calls.lessons_max` (12) lessons that every later call is told. `/lessons` lists them;
  `/lessons forget 2` removes one. One message only when it fixed or learned something; `calls.review` off stops it.
- **Chat remembers only the chat**: a digest's or research run's answer no longer turns up as "you said" in the
  context of your next message.
- **Safer settings and LaTeX**: the dashboard can't change hidden settings any more (who may talk to the Telegram bot,
  where it connects, AI addresses and models; a whole section at once is refused too), and LaTeX the AI wrote never
  runs commands with `latexmk` either (`-no-shell-escape`, as with `pdflatex` and Tectonic).
- **Long Telegram messages are never cut off**: past six parts, the first five come and then the whole text as a file.
  After a revoked bot token is replaced, messages to you come again without a restart.
- **The event log is trimmed** like the logs (past 10 MB the older part moves to `events.jsonl.1`), and reading its end
  no longer reads the whole file.
- **Google keeps your sign-in** when it refuses a short-lived access key: Kurooto gets a new one and tries again; only
  Google saying the sign-in itself is gone pauses the Google features (any refusal used to).
- Fixes: staged updates (`updates.staged`) broke the update check; turning Handwritten notes off didn't stop its
  15-minute scan; an AI-written `/draft`, or the end of a `/focus`, was lost if Kurooto restarted meanwhile; a missing
  scheduled action was logged with the previous run's result; `kurooto doctor --bundle` says when it can't make the
  zip; `kurooto call` exits 2 when Kurooto isn't running, like `send`, `notify` and `ask-me`; the local page answers a
  bad `Content-Length` with 400; a stopped dashboard server stops listening to events; the settings guide no longer
  reads a module `defaults` attribute that nothing used (it's gone from `Module`).
- **Your own scripts for your AI programs**: list them in `agents.scripts` (full paths) and agy and Claude Code may
  run them unattended, by path or by name; a shell or interpreter (bash, python, node...) is never accepted there.
- **Unattended AI can't run code through a command's options**: the commands agy and Claude Code may run on their own
  no longer include `find`, `git`, `latexmk`, `rg` or `sort`, each of which can start another program through its
  options (a prompt hidden in a mail or a web page could have used them). Searching is the AI programs' own job, and
  Kurooto compiles LaTeX itself: now without a `latexmkrc` from the notes folder (`-norc`), and TeX may only read and
  write beside the document.
- **Calls change your lists properly**: "I don't have that quiz" removes it (a new `remove_deadline` tool; it doesn't
  come back from Classroom, a note or the recurring table) instead of putting the subject on your not-interested list,
  and "I have a quiz on Thursday" is a deadline, not something to remember. The look back after each call checks every
  change you asked for against what the tools actually did, and fixes it with the right tool (including undoing a
  wrong ignore with the new `unignore_topic`).
- **Calls can put things in writing and sync now**: "send it on Telegram" sends it (a new `send_message` tool:
  calls used to promise it and send nothing), and "sync now" / "check Classroom now" starts the same sync as
  `/sync all` (`sync_now`), with the result on Telegram.
- **A quiz that's past is over, not overdue**, and a quiz on a course page is never merged into another subject's
  quiz on the same day (a course page's path names its subject). A bare "Quiz" gets its subject's name, everywhere.
- **Start-by says what to start**: "POTA Quiz 2 (on Tue 27 Oct 10:00): start working on it today, about 2 h of work",
  so a call no longer hears "start today" as "the quiz is today".
- **Turning Phone calls off keeps the calls you booked**: they ring when it's back on; one that came due meanwhile
  isn't rung late, you're told about it instead (Reminders already keeps its own the same way).
- **A bare number is a time, not minutes**: `/remind 9 gym` is the next 9:00 (morning or evening, whichever comes
  first) and `/remind 18 gym` is 18:00; minutes need their unit (`20m`, `in 20 min`), and `/due` reads times the same way.
- **Docs match the code**: the manual's term-note example no longer swallows the Concept graph, Space keeper and
  reserve sections, and it now covers `/new` and the chat's memory, the calls look back (`/lessons`), topic study
  packs, `drive_upload.temp_days`, Exam season as an add-on and the new `/help`; agy is the recommended brain
  everywhere; the privacy page says the call line holds the Android app's message key, holds transcripts while the
  computer is off, and that every call's transcript goes to your AI for the look back; the settings guide drops
  Codex and `kurooto restart` and fixes six descriptions; RELEASING.md says never to rebuild after signing.
- **"remind me friday at 5pm ..." means Friday** (it set the next 17:00): plain-English reminders read a weekday that
  says when ("on friday", "this friday", "friday at 5"; "next friday" goes to the AI), not one in what to remember.
- **Turning Reminders off keeps your reminders**: they come back when it's on again, and any that fell due meanwhile
  come at once, marked late. **`/graph stop` holds** until the next night's start (the retries started batches
  again, and a restart forgot it); `/graph now` goes on sooner.
- **The Settings page shows every core setting meant for you**: AI limits, health checks, AI jobs, sources for
  answers, skills in other AI programs, this computer and the dashboard's port, plus `brain.models`,
  `brain.base_urls` and `subjects.timetable`; Telegram's pairing stays off the page and can't be changed through it.
- **A photo or file with Chat on goes to your AI** (with its caption, or "say what it is" without one) when nothing
  else takes it; with both Chat and Files into notes off, the reply says which to turn on.
- Fixes: the Today page's **+30 min** on a check-in pushes it back half an hour (it moved it to the morning);
  `/class remove mon 09:00` works; temporary Drive uploads are deleted with the account that made them, and one you
  moved out of the Kurooto folder is kept, as the message says; a wake-up call rings its full 5 minutes before it
  counts as missed; each ring reaches the Android app once, not twice; a call's look back sees only that call's
  tools; `/lessons clear` is in the help; **R** toggles Recent only while the notes map shows and you aren't typing;
  the concept graph writes a merge the second look turned down as its own note, finishes books with skipped pages,
  follows the bookmarks for books it starts now, and flags two notes that each generalise the other (it flagged the
  consistent pair); a research digest's papers count as sent only once it reached you; a calendar link (or Google
  account) that fails keeps its last events while the others update; the weekly summary counts only AI requests as
  failed AI requests; the privacy lines of After-class notes, Check-ins, Mail digest and Google say what really
  leaves the computer; `/remind` and `/due` say a bare number is minutes.

## 0.5.7 (2026-10-23)

- **Today page in the dashboard (Alt+T)**: one box for anything (plain words to Kurooto, `j` journal, `.` note, `!` a
  reminder), and the day with buttons: set or skip the alarm, tick or move what's due, snooze or cancel reminders,
  move or skip check-ins, answer open questions, write the journal. Every button is the same action as the command
  and the AI's tool (`/api/act`).

- **Space keeper**: cleans off Kurooto's own old backups (past a total size or age, never the newest), downloads and made
  zips, big logs, old finished AI requests and the concept graph's old before-copies, weekly and on request (`/space`,
  `kurooto space [--clean]`). Only Kurooto's own leftovers are touched.
- **The reserve**: Markdown copies of alarms, deadlines, the calendar, settings (never secrets), add-ons and one guide to
  what an AI program may do, in `<state>/reserve/`, so a request can just open a file (`kurooto reserve`). The AI is told
  to read them instead of running commands.
- **The phone app's QR page always offers the newest app** (it read the copy it was set up with, which only got older).
- **Tools you installed yourself are found at boot** (`~/.local/bin`, `~/.cargo/bin`, Homebrew are put on PATH when
  the service starts with a short one): "restic couldn't start: No such file" after a reboot.
- **A free Gemini key goes further**: when one model's daily free limit is used up, the next of the Flash family
  answers (the answer says which).
- **Renaming your assistant** renames the Telegram bot too and says so once.
- **Concept graph fixes**: a concept dropped after a second look is no longer linked from the notes of the same
  batch (it left broken links); the daily pass takes out Kurooto's own links to notes that don't exist; a run paused
  by a signed-out or limited AI tries again in 20 minutes instead of 3 hours.
- **Concept graph**: cost and request counts (`/graph`), effort goes up for books that need many second looks.

- **GPU reranker for the concept graph**: on a computer with a helper model (an 8 GB card, an Apple Silicon Mac, a
  4 GB card's small helper), the local model judges which of your notes belong with a new concept, from its own
  yes/no probabilities, instead of relying on words and vectors alone. No extra download, no AI requests; where there
  is no helper model nothing changes (`integrate.rerank`, `integrate.rerank_model`).
- **Go past what your hardware suggests, and have Kurooto install it** (`hardware.force_profile`,
  `hardware.extra_models`, `hardware.extra_prereqs`; `kurooto hardware --profile big-gpu-12 --add gemma4:12b
  --install`; the same on the setup page's computer step): Kurooto says plainly what you're going past ("this model is
  bigger than your graphics memory: part of it runs on the processor"), never refuses, checks the disk, then installs
  Ollama, the models and the programs you asked for.

## 0.5.6 (2026-10-23)

- **Concept graph** (Features → Concept graph): when a book has been read, its concepts are woven into your notes: new
  concept notes, links with the relation and a specific reason, "Seen in" lists with pages, and a list of what each
  stretch of a book introduces. Checks that don't trust the AI's own opinion (the quote must be in the pages, no vague
  reasons, no links to nothing, no second note for a name you have) decide what's written; doubtful items get a second
  look by the other AI program or are dropped; nothing is queued for you. Your own text is never changed, one git commit
  per batch. agy and Claude Code can split the work and run side by side (`integrate.roles`). Daily second pass over
  what the reading touched. `/graph` for the state and quality numbers.
- **Book sections found properly**: a margin note like "Section 9.1" is no longer taken for a chapter heading (it made
  every chapter a list of other chapters' sections); batches follow numbered headings and running headers.
- **Less vision work when reading books**: a maths page is read again as a picture only when its text layer broke the
  equations into pieces (`books.latex`).

- **Claude Code as a full brain**: a request run by Claude Code gets the same reach as one run by agy: Kurooto's tools
  and your own GBrain's, writing in your notes, course files and add-ons' skills, reading your Documents and
  Downloads, web pages, and harmless commands, all given for that request only (nothing saved in Claude Code's own
  settings, and none of its hooks, project files or history used). Anything else is refused, so a request can't hang
  on a prompt; a refusal says what was refused. Usage limits say when they reset.
- **`kurooto export-skills on --to claude`**: your skills as /commands in Claude Code (only when you ask).
- **Nothing is agy-only**: agent programs share one interface, so the job queue, the setup test, the hand-over to an
  agent program that has worked here, and the terminal's AI tab behave the same for agy and Claude Code.
- **Codex is gone**: it was never fully supported. A setting that names it is cleared, and the next request says to
  choose another AI in Settings → AI.
- **docs/REQUESTED.md**: what people asked for, open and struck through when done.

## 0.5.5 (2026-10-23)

- **PDFs without Tectonic**: a revision pack is built with the computer's own LaTeX (latexmk or pdflatex) when Tectonic
  isn't installed; the LaTeX file is only sent when there's no engine at all.
- **Files, not paths**: `send_files` sends several files (more than two as one zip), `study_pack` sends a subject's notes
  and course files with a prompt for another AI, and `/studypack <subject> <what it's for>` does the same from chat.
  The AI is told to send files, never answer with `file://` paths.
- **Alarm questions** ("do I have any alarms?", "when is my alarm?") are answered at once from local state, with a
  `get_alarm` tool and an `alarm.md` copy for programs that read files.
- **Classroom**: the backfill window always applies and counts edits; posts it left out aren't marked as seen, so a
  longer window finds them (no more syncing again and again).
- **Hubs**: a home note and a research hub exist from the start, list your courses, and course pages link back, so notes
  aren't separate islands; kept current after Classroom filing and book reading.
- **Books**: found in folders at any depth (`.pdf` in any case), `/books read force` on battery, `books.after_read` runs
  your own command after each book, `books.brain_source` indexes chunks in a GBrain source you name.
- **Dashboard notes graph**: neighborhoods come from your own folders; the graph has a Recent toggle.
- **docs/SETTINGS_GUIDE.md**: every setting, written from the code and checked by CI.

## 0.5.4 (2026-10-21)

- **Android ringtone & heads-up banner fix**: Replaced old `calls` channel with `calls_v2` using system default ringtone and `PRIORITY_MAX` heads-up notification priority; guarded against OEM `SecurityException` on ringtone queries.
- **Android update banner**: Shortened update check throttle to 2 minutes on resume and automatically dismiss the update banner once updated.
- **Sync status API fix**: Added POST handler for `/api/sync/status` and state-file fallback in CLI so `kurooto sync` polls and waits smoothly without false aborts.
- **Cross-platform time zone canonicalization**: Fixed casing lookup in `canonical()` so case-insensitive file systems (macOS/Windows) resolve zone aliases properly.
- **Scrapped legacy `oldphone` bridge**: Completely decommissioned and scrubbed legacy `oldphone` module.

## 0.5.2 (2026-10-21)

- **Setup wizard profile restore fix**: Restoring an existing profile archive in setup now seeds and retains restored feature choices instead of wiping selection.
- **Call line & wake intent disambiguation**: Ordered `call_when` ("call me, I didn't wake up at 12") before general `call_now` pattern to prevent misinterpreting past statements as immediate ringing requests.
- **Call invocation resilience**: Fixed `why` and `due` keyword compatibility in `calls.ring()` call-chain when wrapped by legacy bridges.
- **CI & unit test fixes**: Updated brain recommendation assertions to match `agy` first recommendation, aligned call line test isolation with per-test workspace settings, and fixed ruff formatting checks in CI workflows.

## 0.5.1 (2026-10-20)

- **Gemini free-tier key rollover disabled**: Requests using CLI brains (`agy`) no longer roll over to the free Gemini API key on error, preventing unintended rate-limit exhaustion.
- **AGY recommended brain**: Recommended in settings/setup over raw Gemini API keys; includes warning on free-tier 20 req/day limits.
- **Direct laptop ntfy ringing**: Calls and wake-ups publish sealed encrypted payloads directly to ntfy from the laptop as well, ensuring ringing works reliably even when Cloudflare Worker egress blocks ntfy.sh.
- **Telegram multi-turn memory**: Chat maintains recent turns within 2 hours; supports `/new` and `/clear` to start fresh conversations.
- **Classroom to Git migration & unhardcoded paths**: Classroom files organized cleanly under Vault; `send_file` tool supports classroom folder dynamically without hardcoding paths.
- **Study pack generation**: `/studypack <subject>` bundles materials into a zip for external LLMs.
- **Calls when Google's live voice is down** (Gemini Live answering "503 UNAVAILABLE" made calls fail to start, or hang up)
- Live again first: a start Google refuses for now (503, 429, UNAVAILABLE) is tried after about 1 s and 3 s, each time
  with the next model in `calls.live_models` (new, after `calls.live_model`; by default
  `gemini-3.1-flash-live-preview` and `gemini-2.5-flash-native-audio-latest`). Those models get a session any Live
  model takes (tools that wait, a prebuilt voice or Google's default; `calls.voice_by_model` picks one per model).
  "Reconnecting…" shows meanwhile. A drop in the middle of a call is tried again once.
- Then turn by turn with the phone's own speech: the Android app uses Android's speech recognizer and voice, the call
  page the browser's (Chrome). Same call: its instructions, the check-in's or wake-up's script and the same tools.
  Each turn is answered by your computer (your Gemini key, or the model on your computer with `calls.turn_brain` =
  `local`; never an agent program), or by Gemini on your call line while the computer is off or slow.
- Then text on Telegram, when the phone has no speech recognition or microphone: the same call as messages (a
  check-in stays a check-in); what you type is part of it until **End the call** or 20 quiet minutes. With the
  computer off, it starts when the computer is back.
- Whichever way the call went, its transcript feeds your journal and study logs as before.
- `kurooto doctor`: "Phone calls: voice service" counts Live's failures this week, the retries that worked and the
  calls that went on another way (also in the call status the dashboard reads), and names a model in your list that
  Google says no longer exists.

**Calls by your phone's own speech, by choice** (`calls.voice_mode`: `auto`, the default, `live` or `phone`)
- `phone`: calls go turn by turn with your phone's speech every time, not Live; on Android 13+ with your language
  downloaded, speech is recognised on the phone and the audio stays there. `calls.voice_by_kind` sets it per kind of
  call (e.g. the alarm on `phone`, the evening debrief on `live`). The screen stays on during such a call (phones stop
  listening when it goes off). The manual compares the two (feel, latency, languages, privacy, outages).
- The Android app needs this version for turn by turn; older apps go to Telegram instead.

**Calm by default** (on; `notify.calm.on` = `false` restores the old behaviour exactly)
- Every message that comes by itself records why: the feature, what for, the setting that controls it and what it was
  about. On Telegram it has **Why?** (answered from those records; "No reason recorded" when a script or add-on
  didn't say, never a guess) and **Less of this**: Stop / Fewer / Another time, each changing one setting (the
  feature's own where it has one), with Undo. The phone app, the desktop and calls get the plain message.
- A daily limit: 6 messages and 1 call that come by themselves (`notify.calm.messages`, `notify.calm.calls`). The rest
  waits for one evening bundle at 20:00 (`notify.calm.evening_at`), numbered, with each item's buttons; a call past
  the limit becomes a message (check-ins) or a Call now link in the bundle.
- Never held and never stoppable: the alarm, approvals, your own reminders, a deadline under 12 hours away, anything
  urgent. Answers to what you asked aren't counted.
- Exam season gains a part, on by default: during the period only deadlines, quizzes and the alarm come by day; the
  rest waits for the evening.
- Once a month: "you answered 1 of 19 after-class questions: turn them off?" (Apply / No), only for questions.
- `/calm` (today's count, what's waiting and turned down; `/calm 8`, `/calm calls 2`, `/calm evening 21:00`,
  `/calm off`) and `/why` (the last one). For add-ons: `app.notify(..., why=, setting=, about=)`, `app.ask.ask(...,
  why=)`, `calls.ring/place/schedule(..., why=)` and `jobs.submit(..., why=)` carry the reason.
- **"I'm awake"** (or "I just woke up", "I'm up", even with "call me if you need to …") rings the morning call now,
  planned from the current time, with the morning page opened here. With the Morning alarm on, it's a normal call,
  not the alarm: no snooze and no repeat rings, and an alarm still set for later is mentioned.
- **A time about the past, or about something that didn't happen** ("since I didn't wake up at 12", "as I said I
  would", "was supposed to at 9") is never used as the time of a call, reminder or check-in. Before, "… call me if you
  need to, I didn't wake up at 12" could book a call for 12:00 the next day. If that's the only time in a call or
  reminder request, Kurooto asks when instead of booking.
- "call me at 5" means five o'clock (17:00 when said in the afternoon), not five minutes from now.
- **"cancel that call" / "cancel the 12:00 call"** cancels the booked call it means, or lists the booked calls with a
  Cancel button and their keys. A bare "call" no longer counts as the evening check-in, so "cancel that call" can't
  skip it.
- **`kurooto ask`:** "!command" runs a shell command right there, after echoing it. A line typed as a shell command
  without the "!" ("call-me --cancel …", "systemctl …", "kurooto status") gets "that's a shell command: run it in a
  shell tab, or prefix it with !" and is never sent to Kurooto or the AI.
- Tests no longer see or change a Kurooto installed on the computer that runs them: every test gets a pretend home
  (HOME, the XDG folders, APPDATA, LOCALAPPDATA, KUROOTO_HOME) and no keychain, `loginctl`, `systemctl`, `launchctl`
  and `kurooto` are refusing stand-ins, the running dashboard's port is out of reach, and a test that writes to or
  deletes anything in the real install, its systemd unit, autostart or app-menu entries or ~/.gemini fails.
  Autostart and the app-menu entries made for a given home now take every path from it, the app folder included.
- Time zones are compared by what they mean, not by name: an old name and today's (`Europe/Kiev` and
  `Europe/Kyiv`) are one zone for `kurooto doctor` and your call line, and a zone is saved under today's name (the
  setup page's picker offers those; one saved under an old name is renamed at start).
- Research: a project folder that isn't a git repository yet is a project with no commits to follow; doctor says so
  as a note ("isn't a git repository (no commits to follow): `git init` it, or /repos remove it") instead of
  "repository folder missing", and the Research tab can keep or remove it again.
- Reminders: "remind me at 6 pm: …" no longer keeps the colon ("at 18:00: : …"); a ":", "-", "to", "that" or "about"
  left at the start of the text goes, and `/remind 21:30 - …` too.
- Google: a permission Google grants under its older name (Classroom coursework as
  `classroom.student-submissions.me.readonly`) counts as the one asked for. Every sign-in said "Some boxes weren't
  ticked: your Classroom coursework", and Classroom → notes never turned on.
- Google: which account is which. Every account (main too) is asked for its address; `/google` and the Google card
  list each account with it, the sign-in page names the account it saved ("Signed in with Google as … (main)"), and a
  feature's account box shows the address of the account in use.
- Installers: `KUROOTO_CHANNEL=beta` installs from the beta channel, and the install keeps following it
  (`updates.channel` is saved in its settings).
**The dense dashboard makes room**
- Any pane fills the board: click its name (⤢) or double-click its border; Esc or the name again brings the others
  back.
- A **panes** menu in the board's top-right corner hides STATUS, SYSTEMS, NOTES or TERMINAL (one always stays) and
  the others take the room. It's the setting `look.panes`, so every browser shows the same.
- The pages (Features, Settings, Phone, Research, You, Schedule, Jobs, Activity) open over the whole board instead of
  the short terminal pane. Alt and the underlined letter opens one (Alt+F features, Alt+S settings…), Esc goes back;
  a terminal keeps its own Alt keys.
- Features and Settings have a search box (`/` or Ctrl+F, Esc empties it): it filters as you type, marks the words
  it found and counts what's left; a feature is found by its settings too.
- A feature that's off can be hidden from the Features page (`look.hidden_features`); Show hidden (N) at the bottom
  brings it back, and a search still finds it. Only the page changes.
- Links to other sites in Kurooto's pages (Google sign-in, token pages, guides) open in your default browser, also
  when the dashboard runs in another browser's app window. `look.links_in = here` keeps them in the page's browser.
**A stuck AI request no longer holds up the queue**
- Fixed: an automatic revision pack stayed "running" for 20+ minutes and everything you sent after it waited. agy
  stopped (its tool permission was still being asked), your Gemini key took over, and its next request never came
  back when the network dropped behind a login page: one request could wait the job's whole time (30 min for high
  effort), and a connection cut mid-answer could stop the queue for good. A request to a service on the internet now
  waits at most 3/5/10 minutes (low/medium/high), any failure there is a plain failure, and a mistake inside a job
  fails that job instead of stopping the queue. Which AI is working on a request shows while it runs.
- Two lanes: your own requests and background work (automatic packs, routines, the morning plan, digests) run side
  by side, so your request never waits behind background work.
- A watchdog ends a request with no AI at work and no program running for `jobs.stuck_min` minutes (10), or one still
  going past its time limit plus a grace, as failed, with a plain message.
- Cancel: `/jobs` shows what's running and waiting with Cancel buttons (and `/jobs cancel <id|all>`); `kurooto jobs`
  and `kurooto jobs --cancel ID|all`; a Cancel button on the dashboard's AI jobs page. Cancelling a running request
  stops its program and everything it started.

**Stopping is quick and leaves nothing behind**
- Fixed: restarting Kurooto could take 90 s because a program it had started ignored the stop. When Kurooto stops,
  every program it started (terminals and what runs in them, an AI request's agent program and its helpers, your
  GBrain's server, Ollama if Kurooto started it, add-ons' programs) is asked to stop and killed after 5 s if it's
  still there; programs that left a terminal's or agent program's session behind are found too. Programs it opened
  for you (an editor, a browser, a terminal window) stay open. Running AI requests stop where they are and run again
  at the next start.
- The launcher passes a stop on to Kurooto and waits for it. The systemd unit gets `TimeoutStopSec=20` and
  `KillMode=mixed` (an existing unit gets them at the next starts, once the new launcher runs), the macOS LaunchAgent
  `ExitTimeOut` 20.

**Fixes**
- `kurooto doctor` and the health checks said "your call line doesn't answer" while calls rang: Cloudflare turns
  Python's default user agent away ("error code: 1010"), so the check now says it's Kurooto.
- Practice quizzes: a quiz file without all its parts (brought over by an import) no longer breaks quizzes and the
  quiz part of a call's brief; one part of a call's brief failing never stops the rest.

**Google turns on when you sign in**
- Signing in on the Google card turns Google on (and the Google features you set up that Google has OK'd), also when
  an import left it off.

**Commands of features that are off**
- A /command of a feature that's off answers "Google is off: Features → Google → Turn on" (a skill while Skills is off
  the same) instead of going to the AI. `/jobs`, `/status` and `/help` answer whichever features are on.

## 0.5.0 (2026-10-20)
Includes everything planned for 0.4.0 (below), which wasn't released on its own.

**Kurooto keeps itself working** (on by default; `health.on`)
- Every feature that's on has one health check: how often it should work (Classroom within 26 h, Calendar 12, Notes
  sync and the Notes brain 24, Backups and Profile sync 72) and/or a read-only probe (a Google sign-in, GitHub notes
  token or Cloudflare login that ended or ends soon, a Telegram bot that stopped answering, the link to your call line,
  tonight's alarm, messages stuck in a queue). Only awake, unpaused hours count: sleep, shutdowns, network outages and
  pauses (and battery saver, for work that waits for the charger) are taken out first, so a shut lid is never a
  failed sync.
- A daily pass (`health.when`, 21:00) that's silent unless something is wrong. Tonight's alarm might not ring: a
  message now ("set your phone's own alarm too"). A problem that could make you miss a deadline or exam in the next
  48 h: one message now with a Fix button. Anything else: a "Needs a look" part in the weekly summary (or one Sunday
  message with the summary off). Each problem is told once.
- Five fixes, only of Kurooto's own state: sync now, put timers back, reconnect, set the alarm again (the daily alarm
  is otherwise planned at midnight, which a sleeping laptop misses), send stuck messages. The safe ones run before
  you're told (`health.auto_fix`); after a Fix tap you hear whether it worked.
- `/health` on Telegram, a "needs a look" badge and Fix buttons on the dashboard (Features), `working: ...` lines in
  `kurooto doctor`, and `kurooto doctor --fix <id>`. Add-ons can give their own check (`health_check()`).
- Going offline and coming back now keeps the offline periods of the last 15 days (for the checks above). Google's
  sign-in keeps when Google says it ends.
**Free-tier reserve** (on; nothing waits until a limit is known)
- Kurooto counts AI requests per free limit (each model of your Gemini key, agy, another service) and learns each
  limit and when it resets from Google's "limit reached" answers, instead of a table that goes stale. agy's count comes
  from its own logs, so the runs you type count too.
- Past 70% of a day's known limit (`quota.background_pct`), background work waits in the queue and runs after the
  reset: the Classroom digest, the nightly look back, skill changes, research digests, book and handwritten pages read
  by Gemini. The "how hard is this" question moves to the model on this computer, or the rules. Calls, voice notes,
  the morning plan and your own requests keep the rest; nothing is dropped. `quota.local` = `background` moves
  background work to the model on this computer instead of waiting.
- A used-up limit is one plain line: "Google's free limit for today is used up, resets at 12:30; your calls and alarm
  still work." Your own requests try it last, after the fallback brain.
- `/usage`, `kurooto usage` and the usage API show today's limits, what's used of them, and the requests waiting.
- A daily limit no longer waits a minute and asks again before the fallback; handwritten files that hit a limit are
  tried again later instead of being written off.
**Reminders with the lid shut** (new; off until you turn it on; needs Phone calls and the Android app)
- When your computer is asleep or off, your Android phone still gets your reminders at their time, and a morning
  line with the day's first class and what's due (with that morning's alarm, else at 07:30). Your call line holds the
  next day's items sealed for each phone with a key only that phone has: it keeps times and ids, never the text, and
  your Telegram bot's token stays on your computer.
- Whichever side is awake at an item's time says it, once: your computer claims it from the call line and says it on
  Telegram as usual, or the call line sends it to the phone and your computer, awake again, doesn't repeat it. A send
  the call line couldn't make comes back to your computer.
- The batch goes when your reminders change, every 10 minutes, and as the computer goes to sleep (Linux and Windows).
- The Android app makes its own key the first time it runs and gives your call line the public half; a sealed
  reminder shows as a normal notification. Your call line updates itself overnight (or Phone calls → Set up).

**Exam season** (new; off until you turn it on, and nothing happens without exam dates)
- One card for the whole exam period (the exam periods in Subjects and the exams on your deadline list, from the day
  before the first to the end of the last), told once when it starts. Every part has its own switch on the card,
  with `/examseason` or in Settings.
- Non-critical updates wait until the exams are over; a release marked critical in its signed manifest still installs
  (`tools/release.py build --critical`).
- Every night of the period (21:30), the alarm check from "Kurooto keeps itself working" runs (and the call line's,
  when a leave-by call is set), with its safe fix first: "set your phone's own alarm too" if it might not ring.
- The evening before each exam, one question: where is it, which seat, calculator, ID card (and when, if unknown).
  An alarm to leave on time follows (45 minutes before, or "leave 8:10"): a call that rings like the wake-up alarm,
  or an urgent message without Phone calls.
- Half an hour after each exam, a two-minute debrief, saved as you said it under "Exam debriefs" in the subject's
  course note. No calls during an exam.
- The quiz call before an exam is off unless you pick it for that exam; exam mode's daily practice only calls for the
  exams you picked.
- For add-ons: `Module.card()` and `card_action()` put lines and switches on a feature's dashboard card;
  `app.updates.holds` lets a feature hold back non-critical updates.
**Leave cleanly** (new; only when you run it)
- `kurooto uninstall --revoke` first takes back what Kurooto set up on your accounts: deletes your call line from
  Cloudflare with its keys and stored data (through Kurooto's own Cloudflare sign-in, then signs that out; if it has
  expired, it prints the dashboard steps), revokes each Google account's access at Google's revoke endpoint, and
  clears your bot's webhook, waiting messages and command menu. It links what's left for you (the GitHub token page,
  the Gemini key, `/deletebot`), then removes Kurooto's keys from the keychain, which a plain uninstall left there.
- `kurooto rotate`, for a lost phone or a backup with your keys that got out: new keys for your call line (this
  computer's key to it, the key that signs call links, the phone notification key and channel, the Web Push keys),
  deployed to the same address; the old keys come back if the deploy fails. The call line then forgets every paired
  phone, its call links and open pairing codes, and the running Kurooto prints a pairing link and QR code to pair your
  phones again. The keys only you can replace come from the health checks' credential list.
- The call line forgets its paired phones, call links and pairing codes whenever its call-link key changes (after an
  update it only notes the key, so nothing is unpaired).

**Wrong button and test cases** (new; off until you turn it on)
- A Wrong button under replies to plain-English requests and under the AI's answers, and `/wrong` right after a
  reply: the request is kept as a case with what Kurooto did, the time and the settings that decided it. Short
  requests nothing understood (they went to the AI) are kept too; long ones and anything about health, money or
  passwords never are.
- Once a month the look back shows the phrasings that came up most, each with "Make it a test case". Say what you
  meant in words Kurooto understands ("what's due"), or "the AI": it becomes a test case and the phrasing is taught,
  only if every test case that passed still passes. Requests that send, delete, call, ring or approve are never
  learned this way. `/wrong <what you meant>` teaches at once; `/cases` lists what you taught, with Unlearn.
- `kurooto cases` lists them, `kurooto cases check` runs them, `kurooto cases export` writes a pytest file that
  replays each request at its own time and settings. All of it stays on this computer: not in backups, Profile sync
  or the diagnostics zip; cases not reviewed are forgotten after 30 days.

**Start-by dates and crunch weeks** (new; off until you turn it on)
- Each deadline gets a size from what it is (a problem set an evening, a report 2-3 days, a quiz 2 h, an exam what
  you set for its subject; a subject's first exam asks once), corrected with one tap. Working back from your free
  time (each day's window less classes and calendar events, and a share of the rest), each gets a start-by date;
  later deadlines push earlier ones back.
- From its start-by date the morning plan raises it (the morning page, the wake-up call, the plan drafted before the
  alarm), with one "Time to start" message on the day for the big ones.
- The Sunday summary flags crunch weeks: "week of 9 Nov: about 14 h of work, about 9 h free". `/startby`, "when
  should I start the lab report?", "any crunch weeks coming?". An estimate, local arithmetic only, no AI.
**Class packs** (new; off until you turn it on)
- `/classpack export` turns your section's setup into one small `.kurooto-course` file: subjects, timetable (lab
  batches and electives), term and exam dates, holidays, recurring quizzes, dated exams and each course's attendance
  rule (75%, labs counted separately, unless it says otherwise). From your setup, or from one term note alone
  (`/classpack export from terms/section-b`): the term note gains optional Type and Batch columns, and Recurring
  quizzes and Attendance tables. The maker gives the day it was checked against the official timetable before the
  file is made; it's stamped in the pack and the file comes to their Telegram to forward.
- A strict format: names, keys, notes, skills, links, contact details and skips have no place in it, and a file with
  any of them is refused whole, with the reason. `kurooto classpack check FILE` checks one.
- Send a pack to your bot: a review (when it was checked, what it means for you), tick your electives and lab batch,
  change any rule ("la 80", "la labs together", "la quiz off"), Import. It sits under your own setup (yours wins),
  writes nothing into your notes, and its quizzes and exams reach Deadlines. Attendance rules are kept per course for
  an attendance feature to read.
- Importing again after a reshuffle lists what changes for you first and keeps your choices. `/classpack`,
  `/classpack set`, `/classpack remove`, `/classpack undo`; `kurooto classpack export|import`.
**Attendance and standing** (new; off until you turn it on)
- `/attendance`: each course's attendance against its rule (75% unless you set another; labs counted on their own),
  with how many more classes you can miss: "Linear Algebra 82% (23/28), you can miss 3 more this term". Every class on
  your timetable counts as attended unless you `/skip` it; holidays, exam periods and the days after the last day of
  classes don't count. Everything is labelled an estimate.
- `/attendance set la 23/30` corrects drift from the official register; `/attendance rule la 80`, `/attendance rule
  labs 100`, `/attendance lab thu 14:00` (a slot that's a lab), `/attendance since 2026-08-03`.
- `/skip` asks first (Skip anyway / Don't skip) when a skip would leave a course under its rule; `/skip la anyway`
  doesn't ask. Calls tell you before marking such a skip. "can I skip LA on Friday?" answers without marking it.
- One line in the Sunday summary.
- `/standing` adds marks, after a "Set up marks?" question: weightage (`/marks la weights midsem 30, endsem 70`),
  scores (`/marks la midsem 21/30`) and grade lines (`/marks grades A 85, B 70`) give what you'd need on what's left
  for each grade, also an estimate.
**Staged updates and withdrawn versions**
- A version its maintainer withdrew (the signed yank list on the release site, `tools/release.py yank`) is never
  installed: not when found, not when it was already downloaded for the night, and not with `kurooto update --now`.
  The last list read is kept, so it stays refused while the site can't be reached.
- `updates.staged` (off until you turn it on): a new version installs only once it has been out 48 hours
  (`updates.wait_hours`), and never in an exam period or within a day of a quiz or exam (`updates.exam_hold`). A
  release signed as critical (`tools/release.py sign --critical`) skips both.
**First-week quests** (new; off until you turn it on)
- For the first seven days, one short message a day with one thing to try, each leaving something real (tomorrow's
  classes, a deadline, a reminder, a doubt, a quiz, a study session, a check-in answer, a journal entry). Only for
  features that are on and pass their checks, and never one already done. Replying with the thing does it.
- Skip this one moves on; Stop these, or a day's quest left alone, stops them for good. `/quests`, `/quests stop`.
**Doubt queue** (new; off until you turn it on; needs Subjects)
- `/doubt la <the doubt>`, or "I have a doubt about eigenvalues", adds a line to the subject's doubts note
  (`<subject>/doubts.md`, a new `doubts` kind in the notes layout). The subject is the one named, else the class on now
  or just ended, else buttons ask.
- Half an hour before the subject's next class (`doubts.before_min`), its open doubts arrive with a Tick button each
  that ticks it in the note. `/doubts [subject]`. No AI answers.
**Try it on the setup page**
- Once your AI passes its test, the setup page's AI step shows a chat box. What you type goes through the same handler
  as a Telegram message, before Telegram is set up: "remind me in 2 minutes to stretch" pops up on this computer, and
  questions go to your AI with the answer shown in the box. Nothing goes to Telegram or your phone.
**Hint ladder** (new; off until you turn it on; needs Subjects)
- A problem photo with `/hint la` (or the problem typed after it): the idea first, then the setup and the key step one
  tap at a time; the full solution only when asked. Each step names the lecture note the problem belongs to.
- The course's AI policy is asked the first time per subject and kept as an `AI policy: ...` line in its course note;
  "no full solutions" ends at the key step, "no AI help" sends nothing to the AI. The shipped `hint` skill writes the
  ladder (yours replaces it); an answer that isn't in steps is never passed on.

## 0.4.0 (part of 0.5.0)

**Books and PDFs** (new; off until you turn it on)
- Reference books and PDFs per subject: send one on Telegram with "book for <subject>", add it on the dashboard, or
  drop it in the subject's books folder. Books live outside your notes (`files.folder`, or Kurooto's data folder).
- Read at night on the charger, page by page, the best way for each page: the PDF's own text (Poppler, or Kurooto's
  built-in reader), Tesseract OCR for scanned pages, or a local vision model that writes the maths in LaTeX. Gemini
  only if you turn on `books.gemini`. It stops at 07:00 or when you unplug and carries on the next night.
- Each book gets an index note in your notes (`<subject>/books/<book>.md`: chapters with their pages); its text, with
  page markers, stays in Kurooto's data folder, and goes into the Notes brain when that's on.
- `/books` (per subject, how far reading got), `/books read now`, `/books stop`, `/books folder`, `/books setup`.
- Tesseract and Poppler join the things Kurooto can help install (winget for your user on Windows, Homebrew on a Mac;
  on Linux your package manager, which Kurooto never runs for you).

**Notes from every source**
- The source mix: how much books, Classroom materials and your own class notes each count when the AI writes notes,
  per subject (`/books mix <subject> book 30 classroom 30 own 40`, or an order: `prefer own book classroom`). Only the
  sources a subject has are used; the shares grow to fill the gap.
- `/study-log`, Classroom → notes, `/pack`, `/add-to-notes` and the new `/exam-prep` draw on all three through the AI's
  `course_sources` tool and cite where each part came from: (book: <title>, p. 123), (Classroom: <post>),
  (your notes: [[<note>]]). Your own words are quoted, never reworded.
- `/exam-prep <subject>`: brings a subject's exam prep up to date from everything there is, also without Classroom.

**Handwriting on an 8 GB graphics card**
- Handwritten notes are read by a model on your computer whenever there is one: the 12 GB vision model, or now the
  8 GB helper model (gemma4:e4b reads handwriting), or one you name (`handwritten.local_model`). PDFs too, not only
  photos: page by page with the maths in LaTeX, at night on the charger (`handwritten.pdf_hours`), resuming from the
  next page after an unplug or the morning, and waiting while the graphics card is busy. Gemini only when no model
  here can read them; `handwritten.cloud` = `false` never sends them.
- A changed original updates the same note between `kurooto:handwritten` markers and keeps what you wrote around it.
  `handwritten.keep_original` = `link` links to the original where it is instead of copying it. `/handwritten status`,
  `/handwritten retry`.

**Research**
- arXiv sources in arXiv's own search words (`{"type": "arxiv", "name": …, "query": "abs:… AND (…)"}`), each named
  in the digest; arXiv requests three seconds apart. `research.save_note` keeps each digest as `inbox/papers-<date>.md`.
- Runs a script keeps in its repository (`runs/index.csv`) get a line in the project's log every night
  (`research.repo_runs`). `from kurooto.runlog import Run`: `with Run("name", config=…) as run: run.log(step=…, x=…)`,
  into your notes with a project, else into the repository's `runs/`; failed and interrupted runs keep their error.
- Run links in project notes follow your notes layout. "Remind me tomorrow" for a quiet project is a call at 18:00
  when Phone calls is on (`research.remind_by_call`).

**Revision packs before exams**
- The evening before a quiz or exam with a subject, Kurooto offers a revision pack (**Build it** / **No thanks**), or
  builds it by itself with `skills.auto_pack` = `auto` (`off`: never).

**Your own GBrain**
- `gbrain.managed` = `false` uses a GBrain you already run (Postgres or PGLite; `gbrain.exe`, `gbrain.home`) instead
  of Kurooto's own: Kurooto only searches it, adds pages through gbrain's commands, keeps your notes' source in step
  (`gbrain.source`) and runs the nightly steps you choose. It never inits, migrates or reconfigures that brain.
- `gbrain.upkeep_steps`: choose the nightly upkeep's steps (GBrain's phase names; `purge` is never run).
- `gbrain.agy_mcp`: after your approval, agy gets your brain's own MCP server ("gbrain", `mcp(gbrain/*)`), keeping an
  existing registration and your own allow-list picks.
**Google**
- **Several Google accounts** (a personal one and a school one, say): each feature uses the account you choose on its
  card (a new name signs that account in) or with `/google use <feature> <account>`; each account is asked only for
  what its features need. `/google` lists them; `/google forget <name>` removes one.
- **Google Calendar**: Calendar can read your Google calendars through Google's Calendar API, from one account or
  several, for accounts without a secret iCal address. Other people's shared calendars are left out.
- **Private events are "Busy (private)"** wherever Kurooto shows or tells them (Google's Private visibility,
  `CLASS:PRIVATE` in iCal, or `#private`); their title and place aren't kept (`calendar.mask_private`).
- **Class calendars**: `/cal classes Timetable` makes that calendar's events classes (no calls, in your day's classes,
  the after-class question when the title names a subject).
- **Mail digest by email**: each digest also comes to your own inbox, sent from the account you choose, only ever to
  that account's own address; held back if it mentions confidential material.
- **Drive upload**: `kurooto send FILE --to drive` (and the AI's send_file) puts a file in a Kurooto folder in your
  Drive and sends the link; files over Telegram's 50 MB go there by themselves. It sees only files it made.
- The Agent plan calendar can live on another account (`/google use plan personal`).

**Four settings for doing it your way** (defaults unchanged)
- `availability.night.alarm_only`: only a night with the alarm set holds calls (bedtime to the alarm); with no alarm,
  nothing holds them overnight. Off by default: the fixed night hours (23:30 to 07:00) still hold calls without one.
- `deadlines.plan_h` (72): how far ahead "due soon" looks, for the wake-up call's plan, the morning page, the call
  brief, `/status` and "what's due soon?".
- After-class notes for some subjects only: `capture.subjects` (ask only after these; empty: all) and
  `capture.skip_subjects` (never after these), by short name, full name or alias.
- Mail digest by Gmail search: `/mail query -category:promotions -category:social` (`mail_digest.query`, empty by
  default) reads the mail a Gmail search matches. Your never-read list, the not-interested list and the confidential
  check still come first, and personal mail among it is only counted, never summarised. `/mail query off` clears it.

**Your term note, read live**
- `/term note terms/2026-autumn` (`subjects.term_note`): Kurooto reads your timetable, holidays, exam periods, last day
  of classes and a key-dates table from one note, again whenever it changes. Its classes and subjects join yours (a
  code next to a subject becomes a short name), and its quizzes and exams, plus deadlines that name a subject, reach
  Deadlines, kept once with the same thing from your notes, calendar or Classroom. A pattern (`maps/semester-*`)
  follows the current term's note; `auto` is `terms/*`, or `maps/semester-*` in the zettelkasten layout. The format
  is in the manual; `/term-setup` writes notes in it. `/term note off` undoes it; your note is never changed.

**Smaller things**
- The recurring-quizzes table skips any header row ("Course" instead of "Subject", or the row above `| :--- |`), so
  a renamed header no longer asks "which day?".
- With `quiz.by_call` and Phone calls on, `/quiz` and "quiz me" ring you straight away ("here" keeps it on Telegram).
- The dashboard's notes map opens a note with your own program: `notes.open_with`, e.g. `kitty nvim {path}` (no
  shell; the default app when it's empty or the program is missing).
- `kurooto ask-me "…" --then "CMD {answer}"` runs a command with your answer once it comes ({answer}, {id}), in the
  background or with `--wait`; never through a shell, and only from a terminal or script.
- Telegram's "/" menu lists the commands of the features you have on and your skills, kept up to date
  (`telegram.menu`); `/term_setup` style names run the skill with dashes.
- Add-ons: `processes_intermittent = True` on a feature whose programs only run now and then (a backup run, a nightly
  job): its dashboard cell and `kurooto top` line say "idle" instead of a grey "not running", and "running" with the
  figures while one runs.

## 0.3.0 (2026-10-20)
The [manual](docs/MANUAL.md) has the detail.

**Kurooto Terminal**
- `kurooto term` (off until you turn it on): your AI's program, your shell, Kurooto chat and its log in a terminal
  window of its own, with `kurooto top` beside them, in Kurooto's colours. kitty on Linux and macOS (yours, or the
  official kitty in Kurooto's folder, no admin), Windows Terminal on Windows (Kurooto's profiles and colour scheme as
  a fragment, no admin); fish when you have it (or the official fish in Kurooto's folder).
- An app-menu entry, and `kurooto term --shell` for just your shell in Kurooto's colours.
- An opt-in "make Kurooto my default terminal", with a clear undo: opening a terminal then gives you that themed shell
  (`terminal.default_opens`: `layout` for the whole window).
- `kurooto ask` gets the chat tab's look: the spaced name, examples and a `kurooto ❯` prompt.

**Dashboard and `kurooto top`**
- A new **dense** layout, the default on screens 1280 px wide or more: one full-screen board with each pane's name in
  its border.
  - STATUS is a btop-like monitor: history graphs, every core, a memory breakdown, the graphics card, network, disks,
    processes with Kurooto's own marked, study today and projects.
  - SYSTEMS has today, what's due, the AI's corner and recent events round the cells, the hours on the ring, and each
    feature's own programs on its cell. The cells' words sit outside them and never overlap, however many features
    are on: a crowded ring becomes two, and labels move a little (with a hairline to their cell) or shorten.
  - NOTES shows folders and recent edits.
  - The terminal below has its tabs and every other page in its border, and a **kurooto** tab for plain English
    without the Terminals feature.
  - `look.layout = roomy` keeps the earlier layout, which narrower windows get by themselves. `look.projects` lists
    the git folders the board follows.
- Settings shows a list to choose from, with a line of help, where a setting has fixed choices (the palette, the
  dashboard's layout, the notes layout).
- Settings → Starting: start Kurooto when you log in, or (Linux) when the computer starts. Windows and macOS show that
  they start at sign-in.
- `kurooto top` is laid out like btop, with the same figures as the dashboard: history graphs, every core, speed,
  temperatures and fans where the computer has them, memory and swap, the graphics card, network, disks, battery,
  processes (sort with `c` / `m`), and Kurooto's features, call line, today, what's due, study and projects.

**Colours**
- A third palette, **system**: Kurooto's pages take this computer's own accent colour and light or dark mode, and
  follow them when they change. It reads Material You colours from matugen (end-4's Hyprland setup and others), pywal,
  KDE, GNOME 47+ and GTK on Linux, and the accent colour on Windows and macOS. The setup page recommends it when it
  finds your colours (step 2, Colours); Settings → Look → `look.palette` changes it. Text is always made readable
  (WCAG AA). When nothing is found, it looks like kuro.
- `look.theme_file`: a kitty theme or a matugen or pywal `colors.json` of your own, used instead of the desktop's.
- The rose palette's light version: its pink and coloured text is darker, so it's readable on the light background.

**Setup page**
- Each step says what it's for and what happens if you skip it; a step you passed but haven't finished shows "!".
- Words like API key, token, repository, iCal, Cloudflare, GBrain or agy have a one-line explanation: tap the dotted
  word.
- The time zone is picked from a list as you type; a name it doesn't know is caught before you go on.
- AI step: one **Save and test** button for a key, progress while it tests, and what to do when a test fails (for
  each kind of AI). Sign-in windows report back on the page instead of a pop-up.
- Telegram step: an empty or wrong token says what to paste.
- Done step: what's ready and what isn't (with a link back to it), progress for each feature being set up, and next
  steps with an **Open the dashboard** button.
- If Kurooto stops answering, a bar at the top says how to start it again; it goes away by itself.

**Going offline and coming back**
- Kurooto says "going offline (shutting down)" before a clean stop (stop, off, signing out, shutting down; never for
  an update's restart), and "back online (offline since 22:10, 7 h)" after a start, a wake from sleep or a network
  outage ("the network was down from 14:02 to 14:31"), with what it caught up on. Telegram messages that couldn't go
  out while the network was down follow, marked as delayed.
- Nothing for under 10 minutes away; sleeps close together give one message; at night it waits for the morning.
  Settings: `notify.presence`.
- With Phone calls, your call line says "offline since ..." when the computer can't (sleep, a crash, a lost network):
  on the phone app, and on Telegram if you approve giving it your bot's token (asked once). Without a call line there's
  no message for those.

**Check-ins and the computer**
- A check-in day runs from 05:00 to 05:00 (`checkins.day_starts`), so a night check-in after midnight, or one pushed
  past it, stays the evening's (it used to move to the morning), and its journal goes to the evening's day.
- Check-ins by call: with the alarm set and past your bedtime (or the alarm just set by you), the night check-in
  doesn't ring; it moves to the wake-up call, with **Call me now** and **Skip** on Telegram
  (`checkins.asleep_defers`).
- Morning alarm: `alarm.keep_awake` keeps this computer awake from 12 hours before the alarm until it rings (Linux:
  lid closed too; macOS through caffeinate; Windows), so the morning plan is drafted on time. Off until you turn it on.
- Morning alarm: the daily alarm rings even if this computer slept all night. The next one goes to your call line
  as soon as the last one has rung (and at start, and after the computer wakes), instead of only at 00:02.
- Morning alarm: "no alarm tomorrow", "cancel Friday's alarm" or `/alarm skip friday` skips one day and the daily
  alarm comes back after it; "cancel my alarm" skips the morning that's set instead of the daily alarm coming back
  at midnight; "turn my daily alarm off" (`/alarm daily off`) stops it, `/alarm daily 7:00` sets it.
- Stay awake on charger: `awake.lid` keeps a Linux laptop running with its lid closed while plugged in. Off until you
  turn it on. The hold now ends when Kurooto stops, even after a crash.
- Study tracker: it notices you're away on Wayland too (GNOME, KDE, logind, and a watch for change on Hyprland and
  Sway); a locked screen never counts; `kurooto idle away|back` for hypridle and swayidle; and a Research category
  (`study.research_paths`, plus Research's projects).
- Linux: `kurooto autostart boot` (or Settings → Starting) starts Kurooto when the computer starts, before anyone logs
  in (lingering; its keys are kept in the owner-only settings file); `kurooto autostart login` goes back.

**Your notes**
- Notes layout: `notes.layout` picks where Kurooto writes (the `kurooto` layout as before, or `zettelkasten`:
  `dailies/`, `master/`, `sources/<subject>/`, `maps/`, `zettel/`, `projects/`, `digests/`), `notes.paths` puts any
  kind of note where you like, and new notes get that layout's header. The AI, skills and `kurooto note` follow it.
- Files folder: with `files.folder` set, photos, PDFs, revision packs, handwriting originals and Classroom files go to
  a folder outside your notes, linked from them, so they stay out of your notes' history. Unset, nothing changes.
- Revision packs are also linked from the subject's course page.
- Notes sync: a note changed here and elsewhere at once keeps both versions (the other device's in the note, this
  computer's as a "conflict" copy beside it) instead of this computer's winning; `notes_sync.on_conflict = stop`
  stops and asks you instead. A half-finished merge is left alone, and an existing `origin` (e.g. over SSH) is kept.

**From a terminal or a script**
- `kurooto notify` takes buttons (`--button "Label=prefix:ref:action"` or a web address), a link to open (`--click`),
  a reply to an earlier message (`--reply-to`, with `--print-id`), and the kinds `question` and `approval`.
- `kurooto call --list` shows the calls booked for later; `kurooto call --cancel <key>` takes one off.
- `kurooto sync --status` (works with Kurooto stopped) and `kurooto sync --no-wait`; sync everything ends with a
  backup when Backups is on.
- `kurooto ask-me --pending [--json]` and `kurooto ask-me --id <id> --wait`.
- `kurooto usage [days]`: `/usage` in a terminal.

**Skills in agy and other agent programs**
- `kurooto export-skills on` makes your skills (Kurooto's, your add-ons', your own and prompts with `skill: true`)
  slash commands in agy (`--to agy,agents` adds Codex and Copilot CLI). Only Kurooto's own copies are ever changed or
  removed; one of yours with the same name stays, and Kurooto's goes in as `kurooto-<name>`. Kept up to date at start
  and hourly; `kurooto export-skills off` and `kurooto uninstall` remove them.

**Seeing what's going on**
- `/status` also shows today's check-ins, what's due in the next 3 days, the alarm and your last AI requests.
- `/usage` also counts agy itself from its own logs (every run, the ones you type too), with the days it hit its limit.
- `kurooto doctor` asks Telegram whether your bot answers and your call line whether it's up and linked, and no longer
  reports the call line as unlinked just because the check runs outside Kurooto. It also shows your notes layout and
  any problem with its settings (`notes.layout`, `notes.paths`, `files.folder`).
- `/observing` has a **+7 days** button.

**Add-ons**
- An add-on feature can pick which plain-English request a message is before Kurooto's own patterns
  (`classify_intent`, with a 2-second limit and a fall-through), and add lines to `/status` (`status_lines`) and to
  `kurooto doctor` (`doctor_checks`).
- Add-ons can name programs a feature watches (`processes` on the feature): their cpu, memory and uptime show on the
  dashboard and in `kurooto top`, and the cell turns grey when none is running.

## 0.2.1 (2026-10-20)
- Setup page: on a desktop it uses the whole window: the steps sit in a list on the left with what each one is for,
  and feature cards fill four columns instead of a narrow strip. On a phone the steps are numbered dots. Any step can
  be opened from the list, Back and Next stay in view on long steps, and buttons, boxes and cards are tidier, with a
  visible outline when you move through them with the keyboard.
- On laptops whose charger the system names unusually (e.g. ACAD on Linux), Kurooto thought it was on battery while
  plugged in, so battery-saving held back heavy work; it now asks the system directly.
- The confidential-mail page follows your colours (Settings → Look), like the other pages.

## 0.2.0 (2026-10-20)
Many new features, each off until you turn it on. The [manual](docs/MANUAL.md) has the detail.

**Updating from 0.1**
- Nothing new starts by itself: if you set Kurooto up with 0.1, the morning page doesn't open at the alarm, the AI
  doesn't draft a plan before it, deadlines don't ring you six hours before or come from your calendar, an unanswered
  call rings again once (not twice), after-class answers aren't turned into AI study logs, and the nightly look back
  doesn't read your journal or call transcripts, unless you turn them on (or had set them yourself).
- No flood on the first day: deadlines already overdue and research projects already quiet aren't asked about.
- One short "What's new" message after the update, with a link to the manual.
- agy and Kurooto's tools: if you set agy up before, Kurooto asks once (Approve / Deny) before adding itself to agy's
  settings; Deny holds for 30 days. On the setup page, testing agy says it connects the tools.

**Your AI**
- The setup page recommends a **Gemini API key ★** (the simplest, and Google's recommended route for tools like
  Kurooto), then agy, Codex, Claude Code, local models and any OpenAI-compatible service. Existing setups keep the AI
  they chose.
- The setup page says plainly what a free Gemini key means (Google may use and review what you send; 18+; a paid key
  in the EEA, UK and Switzerland) and what using agy through Kurooto means for your Google account.
- FreeLLMAPI is no longer offered; one set up earlier keeps working and shows as "Another OpenAI-compatible service".
- The AI can act, not just answer: every feature's tools (reminders, calls, deadlines, study log, notes, questions to
  you) reach API brains directly and agent programs (agy, Codex, Claude Code) through `kurooto mcp`, a built-in MCP
  server. The notes tools only create, add to and tick; they never change what you wrote.
- `/usage`: AI requests per day per brain over the last week, and usage limits hit.
- Your AI can read your files (notes, Documents, Downloads, Screenshots, Kurooto's Classroom and mail copies) and
  public web pages, write and edit text files in your notes (the previous version is kept), and tell you how your
  syncs are doing (`sync_status`). agy gets the same reach through its allow-list, after you approve it: those
  folders, the web, and harmless commands such as git and latexmk; never `kurooto` itself.

**Questions, approvals and your phone**
- Questions and approvals from features, AI requests and your own scripts, answered anywhere: Telegram buttons or a
  reply, the phone app, or a call; the first answer wins. **Later** keeps one for your next call; `/q` lists the open
  ones. AI requests can ask you a question; your answer starts the follow-up.
- Your phone is a second channel: questions and approvals reach the Android app (Reply box, choices, Approve / Deny,
  Later) and the iPhone Home Screen app ("Waiting for you"), also while the computer is off. `notify.app_kinds` picks
  what else goes there.
- Calls: open questions come up at the start of a call, and approvals that arrive during one are asked there. Nothing
  else rings while you're on a call, and updates wait for it to end.

**Check-ins, mornings and calls**
- The evening check-in call is a debrief (classes, what slipped, open questions, study time, a quiz offer before
  exams); afterwards the AI writes your journal and study logs from what you said.
- A night check-in (off until you give it a time) says goodnight and sets the alarm, or moves to your wake-up call
  with **Tomorrow morning**.
- Unanswered or declined check-in calls become a message with Call me now / Tomorrow morning / Skip; "call me back
  later" keeps it a check-in. Change another day's check-in ("skip Friday's check-in"); `/checkins` has buttons.
- Mornings: the AI drafts your day 20 minutes before the alarm, the wake-up call goes through it, and the morning page
  opens on your computer.
- The night follows your alarm; unanswered calls ring again at +3 and +6 minutes; held calls tell you so and come by
  themselves when the block ends; "call me now".
- Calendar: `#focus` events are focus time; optionally only `#nocall` events hold calls.
- Weekly summary: an optional Sunday review call, written up in your journal.

**Study**
- Deadlines: calendar events that look like deadlines or exams, and recurring quizzes (a table in your notes,
  `/recurring`), join the list; the same thing from two places is kept once.
- Deadlines: the six-hour nudge is a call when Phone calls is on; an "Overdue?" check (Done / New date / Drop); Done
  ticks the box in your notes.
- Not interested (`/ignore`): topics left out of deadlines, and only counted in the mail and Classroom digests.
- Exam mode: on by itself two weeks before a quiz or exam (`/exam`); calls know about it; quizzes come more often.
- Quiz: sessions of several questions, a practice offer the evening before, quizzes by call, quiz check-ins.
- Subjects: term dates and exam periods (`/term`); "skipping LA on Friday".
- After-class notes: answer later on the evening call; photos and files filed next to the class log; an AI study log.
- Study tracker: sessions away from the computer (`/study la 50`, `/study stop`) and a "Study hours" section in your
  daily note.

**Notes and skills**
- Skills: `/journal`, `/study-log`, `/add-to-notes`, `/assignment`, `/connect-notes`, `/term-setup`, `/goodnight`,
  `/morning`, `/morning-prep`; reply to a skill's answer to carry on. A link sent on its own is filed into your notes.
- Your own skills (`/newskill`, `/skills copy`), routines (`/every monday 9:00 /journal plan my week`) and revision
  packs as PDF (`/pack`, with Tectonic, which Kurooto can install for you).
- Quick notes and prompts: `/note`, `kurooto note`, `/prompts`, `/prompt`.
- About you: the profile is editable right after **Build my profile** (setup page, and a new **About you** tab in the
  dashboard), with a preview of the In-brief part that goes along with every AI request; saving keeps the previous
  version. Building again asks first if you've edited it, and never replaces an edit made while it was building.
  `/aboutme` shows the In-brief part.
- Remember: `/remember`, "remember that ...", and on calls; kept in `about-me/how-to-help-me.md`, which you edit and
  which wins. Health, money and passwords are refused.
- Nightly look back: reads your answers, check-ins, call transcripts and journal; suggests settings, how-to-help-me
  lines, things to watch, skill changes (shown before saving) and ideas. Apply / Observe longer / No. `/observe`,
  `/observing`, `/lookback`.
- Notes brain: timelines (`/timeline`), an optional nightly upkeep and a weekly checkup.
- `kurooto send FILE`: a file to your Telegram; the AI can send you files from your notes.

**Google**
- Classroom → notes: new materials, coursework, announcements and attached Drive files filed into your notes by the AI
  (a note per lecture, a course page, an exam-prep note that Quiz uses); dates go into Deadlines.
- Mail digest: twice a day, sorted into Needs action, People, Courses, Opportunities and Admin. It reads only the
  senders, domains and labels you choose; mail marked confidential (anywhere in it, standard confidentiality footers
  included) and your never-read list are only counted, never summarised or answered with an AI draft. Optional local
  mode (`mail_digest.confidential = local`): a local model summarises confidential mail on this computer, kept only
  in Kurooto's data folder (dashboard → Features → Mail digest → Confidential mail); dates found there are offered
  (`/mail confidential`), never added by themselves.
- Email reply drafts with Send / Edit / Discard: nothing is sent without your tap.
- Agent plan calendar: time blocks Kurooto plans with you go into a calendar of its own (`/blocks`).
- Each Google feature asks for its own permission and turns on by itself after the sign-in.
- Setting up Google is beginner-proof: a step-by-step guide in the manual (every screen of Google Auth Platform,
  with links), and the setup card has a numbered summary, copy buttons for the values Google asks for, and a file
  button for the client JSON. The site has a privacy page (made from docs/PRIVACY.md).

**Your setup, kept safe**
- Backups: a daily zip in a folder you pick (an external drive, a cloud-synced folder); `kurooto restore`, which
  never overwrites a note.
- Profile sync: your settings, keys and saved state, encrypted with a passphrase only you know, in your own private
  GitHub repository. Moving to a new computer: "I've used Kurooto before" on the setup page, or
  `kurooto profile restore`.
- Sync everything: `/sync all` or `kurooto sync`. Notes sync also sends notes up after AI requests and when Kurooto
  stops.

**Research and your terminal**
- Research projects: a note per project with a log of each day's commits, a hub note, and a question when a project
  goes quiet.
- `kurooto runlog` (experiment runs with their config, metrics and exact code state), `kurooto watch -- CMD` (a
  message when a long job ends), `kurooto top` (a status board), `kurooto logs`, `kurooto ask` (plain English),
  `kurooto call`, `kurooto ask-me` and `kurooto ask-approval`.
- Terminals in the dashboard (off by default): your AI program, a shell, `kurooto ask` and the log.
- Your add-ons: your own features, skills, prompts and default settings from a folder of yours.
- On Linux, the dashboard only answers your own user account.

**Look**
- Kurooto's pages are deep green now, like the website: the setup page, the dashboard (its drawings too), the morning
  page, and your call line's pages and icon. The old colours stay available: Settings → Look → `look.palette` = `rose`.
- Warnings and errors have their own colours (amber and red), never the accent colour.
- The dashboard's ring gives every feature a short label and its own colour.
- The README and the website show the dashboard, the setup page, the morning page and your phone, from a demo with
  made-up data.

**Fixes**
- The setup page's "When this laptop is on battery" choice was refused; it's saved again, and Settings can change it.
- The dashboard keeps its address after a quick restart or an update (macOS and Linux).
- `kurooto stop` stops Kurooto the normal way first (Notes sync sends up what's left), then forces what's left;
  `kurooto start` says where the page is; `kurooto on` doesn't wait for a service manager that isn't there.
- After `kurooto update --now`, or an update that was rolled back, the dashboard no longer says "update ready"; a
  rollback sends one message saying so.
- The 05:10 call-line update after an update never opens a Cloudflare sign-in page by itself; if the sign-in expired,
  you get a message (calls keep working on the old version).
- A 24-hour time is taken as written: "/checkin midday 04:30" is 04:30, not 16:30.
- /status and `kurooto top` say what's coming in words, not internal names. "Overdue?" isn't said twice.
- The ★ Starter set no longer includes the notes brain (a 0.5 GB download; its card says so). Exam mode's daily
  practice check-in is off unless you give it a time (`quiz.exam_daily`).
- `kurooto doctor` warns when your time zone (Settings → You) isn't this computer's.
- Kurooto's job and schedule databases are readable by your account only, like its other state files; the installer
  starts Kurooto without its own temporary Python environment on the PATH.
- The phone's call page: the "Waiting for you" link no longer grows to fill the screen.
- "skip Friday's check-in" (and "no calls on Friday", "skipping LA on Friday") changed today's instead.
- The phone app only ever got rings; the phone channel is now wired up.
- The notes brain's sync no longer holds up the rest of Kurooto, and GBrain no longer checks for its own updates.
- Long requests to agy no longer fail on Windows' command-line limit.

## 0.1.6 (2026-10-20)
- **Phone calls couldn't be set up at all**: building the call page always failed. Fixed; setup now goes on to the
  Cloudflare sign-in. The Phone calls card lists what's needed in order (a free Gemini key, needed even when agy
  answers your messages; a free Cloudflare account; then pairing your phone, which is where the app comes from) and
  has a **Set up now** button.
- **Google sign-in could seem to do nothing**: the browser blocked the pop-up. There's now always an **Open Google
  sign-in** button, the card notices when you're signed in, and each way it can fail says what to do (including
  boxes left unticked on Google's consent page).
- Setup logs no longer vanish when the page redraws, and a refused setup says why.
- Setting up local AI models on Linux could get Kurooto killed for running out of memory: Ollama's download was
  unpacked in memory. It's now unpacked straight from disk, and the space check counts Ollama's real size.
- Setup: click anywhere on a feature card to tick it, and the boxes are bigger.
- A request to the AI could now and then vanish or fail when the setup page or the dashboard checked on it at the
  same moment (mostly on Windows).
- `kurooto start` works on computers where systemd's user session doesn't (WSL, containers).

## 0.1.5 (2026-10-20)
Everything since 0.1.1, in one update.
- **`kurooto stop` didn't stay stopped** on Linux and macOS (the background service restarted it 10 seconds later),
  and `kurooto start` / `on` could start a second copy beside it: both now go through the service manager.
- **`kurooto` was an "unknown command"** on computers that already had uv: Kurooto now puts its folder on the PATH
  (your user PATH on Windows, fish, bash and zsh) when it installs and whenever it starts, and the installer says
  how to use it in the terminal you installed from.
- **Telegram setup could wait forever** after pressing Start: the page now says why (another program using the bot,
  a webhook, a revoked token, an expired link, no internet), offers the fix, and always shows the message to send by
  hand. Running setup again while Telegram is on no longer swallows the Start message.
- **"Build my profile" failed with agy**: text-only work now tells agy to answer with text only.
- **agy and a Gemini key back each other up**: if one can't do something (refused, limit reached, signed out,
  failed), the other answers, and a line at the end says which. Without a Gemini key, the message says what to do.
- Long requests reach agy through a file, so profile builds work on Windows too.
- About you: the profile is editable right after **Build my profile**, on the setup page, with a preview of the
  In-brief part that goes along with every AI request; saving keeps the previous version. Building again asks first if
  you've edited it, and never replaces an edit made while it was building. `/aboutme` shows the In-brief part.
- The setup page recommends the Gemini key first (★); agy is second, with a plain note about it.

## 0.1.1 (2026-10-20)
Fixes, delivered as the first automatic update.
- A check-in call that comes due during a class, a hold, focus or the night now waits until the block ends, or comes
  as a message if that's too late for today.
- What you say on a check-in call reaches your journal again.
- Checking Kurooto (`kurooto doctor`) while the AI is working no longer makes that request run a second time.
- A landing page at avtarfr.github.io/kurooto.

## 0.1.0 (2026-10-19)
The first release, for friends.
- One-line install on Windows, macOS and Linux (per user, no admin), signed releases, a setup wizard that reads the
  computer and recommends settings, and installs what each feature needs (with a storage check).
- AI brains: Antigravity (agy), Gemini key, ChatGPT/Codex, FreeLLMAPI, Ollama, any OpenAI-compatible service, and
  Claude Code (Advanced); a fallback brain; effort picked per request.
- Features (all opt-in): Telegram, Chat, Reminders, Check-ins (by message or call), Deadlines, Subjects and timetable,
  Quiz, Weekly summary, Files into notes, Notes brain (GBrain), Local AI models, After-class notes, Nightly look back,
  Phone calls (your own call line; Android app; iPhone web app), Morning alarm, Voice notes, Stay awake on charger,
  Calendar, Notes sync, Google (Classroom, Gmail drafts), Handwritten notes, Study tracker, Research (a digest of new
  papers from arXiv's 155 fields, bioRxiv, medRxiv, PubMed and any feed, with its own dashboard tab).
- About you: prompts to run in all your other AI accounts, their reports brought into Kurooto, and a profile built
  from them that every AI request starts from.
- A local dashboard; `kurooto doctor` and a redacted diagnostics bundle.
- Laptops: a battery saver (Telegram keeps working; heavy work waits for the charger and runs when plugged in),
  `/pause` and `/resume`, and `kurooto off` / `on` (with a Kurooto entry in the app menu to turn it back on).
- Automatic, signed updates with rollback.

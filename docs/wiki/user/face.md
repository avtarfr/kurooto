# Face presence: greet you at your desk

Kurooto can learn your face, on your computer only, and greet you by voice when you sit down at your desk after a
while: what's next today and what's waiting. Then it listens for your answer, so you can say "what's on today?" without
its name. Someone else's face never triggers it and is never kept. Off until you turn it on, and nothing watches until
you've enrolled your face yourself (0.8.10).

It's a convenience, **never a lock**: a face match never approves, unlocks or allows anything.

- [Setting it up](#setting-it-up)
- [Enrolling your face](#enrolling-your-face)
- [What "training" means here](#what-training-means-here)
- [The report and the grade](#the-report-and-the-grade)
- [Testing it](#testing-it)
- [Watching for you](#watching-for-you)
- [The greeting and the conversation](#the-greeting-and-the-conversation)
- [When you step away](#when-you-step-away)
- [Learning over time](#learning-over-time)
- [Forgetting your face](#forgetting-your-face)
- [Privacy](#privacy)
- [It's not a lock](#its-not-a-lock)
- [Commands](#commands)
- [Settings](#settings)
- [Licences](#licences)
- [Troubleshooting](#troubleshooting)

## Setting it up

**Features → Face presence → Turn on**, then **Set up** (on the card or the Face page). It downloads once, and says
how much first:

| Part | What it's for | About |
|---|---|---|
| opencv-python-headless and numpy | the camera, finding faces, recognising yours | 0.14 GB installed |
| YuNet (`face_detection_yunet_2023mar.onnx`) | finding faces in a picture | 0.23 MB |
| SFace (`face_recognition_sface_2021dec.onnx`) | turning a face into 128 numbers to compare | 38.7 MB |

The two model files come from OpenCV's model zoo (pinned to one version and checked against their fingerprints), the
package from PyPI. After that it works without the internet, on your computer's processor (no graphics card needed,
so it never competes with a local AI model for it).

**No internet on this computer?** Put the two `.onnx` files and the package's wheels in a folder, then
`kurooto face install-from FOLDER` (or **Install from a folder** on the Face page). On another computer:

- the models: [YuNet](https://media.githubusercontent.com/media/opencv/opencv_zoo/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/face_detection_yunet/face_detection_yunet_2023mar.onnx)
  and [SFace](https://media.githubusercontent.com/media/opencv/opencv_zoo/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/face_recognition_sface/face_recognition_sface_2021dec.onnx);
- the wheels: `pip download opencv-python-headless numpy --only-binary :all: -d FOLDER` (for the same system and
  Python version as this computer).

Files whose fingerprint doesn't match are skipped and named; it then says what's still missing.

**The camera:** the first ordinary webcam is used (infrared ones are skipped). `face.camera.device` picks another, by
number or part of its name; a change takes effect within a few seconds, without a restart. A virtual camera (an
add-on's phone camera, OBS's) can be used while another program feeds it, and with no camera chosen, one that's in use
leaves the next one free. On macOS and Windows, the program that runs Kurooto needs the system's camera permission
(see [Troubleshooting](#troubleshooting)); `kurooto face test-camera` checks the camera for 3 seconds and prints its
size, speed and light, never a picture.

## Enrolling your face

Open the **Face** page (the dashboard's `face` tab, Alt+E, or "Open the Face page" on the card) and press **Start**.
The camera's light comes on; the preview is drawn on the page only, never saved. Nine short steps:

| # | Step | What to do | Samples | Can skip |
|---|---|---|---|---|
| 1 | front | look straight at the camera, at your usual distance | 8 | no |
| 2 | left | turn your head a little to your left | 5 | no |
| 3 | right | a little to your right | 5 | no |
| 4 | up | tilt your chin up a little | 4 | no |
| 5 | down | and down a little | 4 | no |
| 6 | near | lean in closer | 5 | yes |
| 7 | far | sit back | 5 | yes |
| 8 | glasses | put your glasses on (or take them off); "I don't wear glasses" skips it | 8 | yes |
| 9 | light | change the light: the room light off, a desk lamp, the window behind you | 8 | yes |

That's 52 samples. **Finish and train** works once the first five steps are done (26 samples); the last four raise the
grade, and **Add samples** later picks up the steps that are short. Each step has its own meter, and the top one says
"34 of 52 samples · step 5 of 9". Tick **Say the steps aloud** (with Voice on) and Kurooto reads each step and the odd
nudge. **Pause** and **Discard** do what they say; Discard drops every sample at once.

**Every frame is checked**, and the first thing wrong is shown under the preview:

| What it says | What to do |
|---|---|
| No face found: look at the camera. | face the camera |
| Two faces: only you should be in view while enrolling. | ask the other person to step out of view |
| Too far: come a little closer. / Too close: move back a little. | adjust your distance |
| Partly out of view at the bottom (top, left, right): … | it says which way to move; tilting the screen helps at the top and bottom |
| Lean in a little closer (60% of the way). | the near step: lean in until it's done; only your eyes, nose and mouth need to stay in the picture, your chin or forehead may leave it |
| Keep your head level. | straighten your head |
| (the step's own nudge, e.g. "Turn a bit more to your left.") | follow it |
| Blurry: hold still for a moment. | hold still |
| Too dark / Too bright | more light on your face; no lamp or window right behind you |
| Move a little: that's the same as the last one. | move a little: each sample should add something |
| That doesn't look like the earlier samples. Is someone else in view? | only you, please |
| The camera sees nothing: is it covered, or the lid closed? | open the shutter or the lid |

Samples are kept in memory only while you enrol; if you don't train within 30 minutes, they're dropped. The camera
closes when you leave the page (after 15 seconds) and after 10 minutes of capturing in all.

**Start over** (on the Face page once you're enrolled) runs all nine steps again from nothing. Your current face model
keeps working until you press **Finish and train**; **Discard** leaves it as it was. After a training (Start over or
Add samples), **Undo the last training** puts the previous model back, until Kurooto restarts (the old one is held in
memory only, never written down).

## What "training" means here

Honestly: **Kurooto doesn't train a neural network.** Face detection (YuNet) and recognition (SFace) are pretrained
models, used as they are. "Training" is three small things done on your computer in under a second:

1. **Your template.** Each sample becomes SFace's 128 numbers. Your template is their average (the centroid), one for
   each condition: your usual look, with glasses, and in other light, so glasses on and off both work.
2. **Your threshold.** Kurooto scores each of your samples against a template built without it (held out, five
   rounds), and scores a bundled set of made-up faces against your template. It then picks the score above which a
   face counts as you, so that about 1 in 1,000 of those made-up faces would pass (`face.recognise.strictness`). It
   never goes below 0.363, the threshold OpenCV publishes for SFace, chosen on real people.
3. **A grade and advice:** how often you'd be recognised at that threshold, and what would help.

Why not a classifier or a fine-tune on top? There's one person (you) and about 50 samples. A classifier would mostly
learn how the made-up impostor faces differ from real ones, not how you differ from other people, and fine-tuning SFace
would need a much bigger toolkit and real face images we can't licence. If a test on real data ever shows a classifier
doing better at the same strictness, it can come later behind its own switch.

**About the made-up faces:** the impostor set isn't in this release yet. Until it is, the threshold is OpenCV's 0.363
plus 0.05, and the report says "calibrated without the impostor set: run the 'someone else' test".

## The report and the grade

After training, and on the Face page later:

- **Recognised:** the share of your held-out samples that pass, overall and per step.
- **The scores:** your median, the threshold ("needs 0.43") and the "unsure" band under it (0.10 lower): a face in
  that band counts for nothing either way.
- **Grade:** **good** (95 % or more recognised, a comfortable margin, and all nine steps done), **fair** (80 % or
  more), or **weak**. A weak model is still used, and the card says "weak model: greetings may miss you; add samples".
- **Advice**, e.g. "Other light: recognised in 4 of 10 held-out samples. Add more samples other light."

## Testing it

On the Face page, **Test** opens the camera for up to a minute and shows each face's score as a number and a bar, with
the two marks (unsure, you), and the decision in words: "You (0.71; needs 0.43)".

- **I'm testing as me:** ten seconds; how many frames recognised you, and whether an arrival would have greeted you.
- **Someone else is in front of the camera:** ten seconds (ask them first); the best score seen and whether any frame
  would have counted as you. A stranger's photo on a phone screen works too.
- **The honest one:** try a photo of *yourself* on your phone. It will probably say "you". That's why face presence
  never unlocks or approves anything.

Only the results are kept (when, how many frames, the best score); never anything of the other person. If it took
someone else for you, it says: "Raise strictness to strict, or retrain with more samples."

## Watching for you

Once you've enrolled, Kurooto looks for you **only while you're not using the computer**:

- **While you type or use the mouse, the camera stays closed.** Your input says you're here. That also leaves the
  camera free for a video call you start (on Linux only one program can use a camera at a time).
- After a minute with no input (`face.watch.idle_s`), right after you unlock the screen or the computer wakes, it opens
  the camera and looks about once a second (`face.watch.fps`; 0.33 on battery). When you start typing again, it gets up
  to 6 seconds to recognise you, then closes. On a computer that can't say how long you've been idle, it looks only
  after an unlock or a wake, for a few seconds.
- A dashboard badge "● camera" shows while Kurooto holds the camera, and the card says "Camera: on (looking for you)".
  The camera's own light is the honest signal: look for it.

**Add-ons** may ask Face presence to keep looking while you type, or to tell them who's in view (where each face
is and whether it's you; never a picture). Then the card and `/face` say "camera on: an add-on is looking" and why.
A hold lasts at most 10 minutes unless the add-on asks again, and everything in the pause list below still stops it.
`face.addons.hold` and `face.addons.watch` turn those off.

**Voice only answers someone in front of it** (`voice.listen.need_face`, on): while [Voice](voice.md) listens, it
keeps the camera looking, even while you type (the card says "camera on: voice: who's talking"), and a turn is
answered only when a face close to the camera (about your desk distance, `voice.listen.face_near`) and facing it
(`voice.listen.face_yaw_deg`) was seen while it was said. Someone on a phone call across the room isn't answered. The
pause list below still comes first; then `voice.listen.need_face_fallback` decides (`voice`: the voice rules alone;
`none`: nothing by voice). Only times and counts are kept, in memory. This hold isn't an add-on's, so
`face.addons.hold` doesn't stop it; `voice.listen.need_face` with `voice.listen.look_to_talk`, or muting Voice, does. While it holds the camera, a video
call app can't use it.

**Look at it to talk** (`voice.listen.look_to_talk`, on): look straight at the camera for about a second and Voice
starts listening as if you'd said its name ([Voice](voice.md#look-at-it-to-talk)). Anyone's face counts
(`voice.listen.look_anyone`, 0.8.18; off: only yours): for the others it reads only which way they look, never who they
are. On its
own it goes by which way your head points; with the eye model and your eyes calibrated (below) it goes by your eyes,
at once. The camera is held while Voice listens for this too, and looks up to 5 times a second then
(`face.watch.look_fps`).

**When the spot to look at isn't the lens** (0.9.0, `face.camera.yaw_offset_deg`, 0): if you're meant to look at
something beside the camera (a drawn eye next to a phone's camera, say), set how many degrees to your right (or left,
negative) of the lens it sits, and a look there counts instead of a look into the lens. About 7 degrees for 7 cm at
60 cm. An add-on whose camera needs it may set it while that camera is in use.

**Calibrating your eyes** (the Face page, under Look to talk, once you've enrolled): **Get the eye model** (2.6 MB, once),
then **Calibrate my eyes**: the camera opens and you look at its lens, head turned to it, for about three seconds. It
keeps four numbers in your sealed face model (where your irises sit in your eyes and how your head was turned), never a
picture; **Clear** drops them. Calibrate again if you move the camera. How it's used: [Voice](voice.md#by-your-eyes).

**Following faces** (`face.track.on`, on): while the camera is open and a dashboard is in sight, the being's eye
follows whoever is in view, not just you: it looks at one person and moves on to another every few seconds, sooner
when someone new appears or someone moves more; with one person it follows them closely, small nods and turns
included. It only knows where each face is and how much it moves (and which one is you); it never works out who
anyone else is. It looks up to 10 times a second then (`face.track.fps`), which costs roughly a tenth of one
processor core while it lasts; it never opens the camera by itself. An add-on can follow faces the same way.

**You've arrived** when it recognises you in 3 of 4 frames within 6 seconds, after at least 20 minutes with no sign of
you (`face.greet.after_absent_min`; a locked screen isn't a sign of you). Unsure frames and other people count for
nothing. A photo propped up in front of the camera doesn't move, so it waits for movement.

**It pauses** (and says why on the card and in `/face`) when: Face presence is off; you haven't enrolled; it isn't set
up; you paused it (`/face pause 1h`); Kurooto is paused, or on battery in pause mode; the screen is locked
(`face.watch.when_locked` to look anyway); you're on a call; focus; the night hours (`face.watch.night` to look
anyway); Kurooto is asleep (0.8.18, `mind.sleep.senses_off`: `/wake`, a message, a tap or a call wakes it, and the
camera with it); you're enrolling; another program uses the camera (checked again every minute); there's no camera; the system
blocks it; it's covered (10 dark frames; checked again every 5 minutes); or its key can't be read.

**A sharper camera** (say a phone's 1080x1440 instead of 480x640) works the same way: faces are found on a small copy
of each picture, how close you are is judged as a share of the picture's height, and the eyes are cut from the full
picture, so only the eyes get sharper. Your enrolment carries over; after the switch, calibrate your eyes again.

## The greeting and the conversation

When you arrive, Kurooto says, in about three sentences, through your speakers:

> Welcome back. Next: Linear Algebra at 14:00, in 40 minutes. Two questions and one approval wait for you. Want to go
> through them?

("Morning." the first time a day before noon.) What it mentions is `face.greet.say`: what's next today, how many
questions and approvals wait (never what they say), one deadline due within 24 hours, and how many messages wait for
the evening (`held`, off by default). It's made by rules on your computer: no AI request, and it's never sent to
Telegram, your phone or your AI. With "what to call you" on your [persona card](teaching-kurooto.md#your-persona-card)
(0.9.0, `persona.templates`), it starts "Welcome back, Sam." while you're alone in view; the name never pushes a part
out of the greeting.

Then the conversation opens for 12 seconds (`face.greet.listen_s`), like after you'd said "Kurooto": "what's next?"
or "yes" goes to your AI without saying its name. Chatter nearby closes it at once and isn't sent. That needs Voice
listening on; without it you hear the greeting only.

**It doesn't greet** when Voice is off, muted or can't speak; during a call, "no calls till", focus, the night, a class
you attend or a calendar event; while Kurooto is asleep or drowsy (with Brain, [its sleep](mind.md#kurooto-sleeps)); while Kurooto is paused; within an hour of the last greeting (`face.greet.gap_min`);
after three a day (`face.greet.per_day`); during exam season's quiet days or a quiet week; or when you turned them
off (`face.greet.on`, "Greet me when I sit down" on the card). Greetings aren't counted against the six messages a
day, and each one, said or skipped, is recorded with its reason (never its words).

**Someone else at the desk:** no greeting at all by default (`face.greet.with_others` = `skip`). `short` says only
"Welcome back." with no details and no conversation; `full` greets as usual. Class and deadline names are never spoken
in front of someone else unless you chose `full`.

## When you step away

Off by default: turn on `face.away.on` (or "Notice when I leave" on the card). With no sign of you for 5 minutes
(`face.away.after_min`) while the camera looks, or with the screen locked that long, Kurooto notes that you've left;
you're back when it recognises you or someone types. Two more switches use it:

- `face.away.hold_desktop`: desktop pop-ups wait until you're back (at most 20), and answers aren't read aloud to an
  empty room (they're on the dashboard).
- `face.away.hold_calls`: while you're away, calls wait as they do during a class (a no-call time), until you're back
  or at most an hour (`face.away.hold_max_min`).

## Learning over time

Off by default (`face.learn.on`, "Learn slowly from confident sightings" on the card). When on, a sighting can refine
your template only when it's very sure (well above the threshold), you're alone in view, the picture is good, it was
part of an arrival and you typed within a minute after, it's been 6 hours since the last one, and it adds something
new. Never from an unsure frame, someone else in view, or a test. At most 30 learned samples (the oldest goes first);
your enrolled samples are never replaced, and the threshold is still measured only on your enrolled samples.

The Face page lists what it learned ("Learned 1 sample on 3 Nov"), with **Undo the last** and **Forget what it
learned**.

## Forgetting your face

Any of these deletes your face model:

- `/face forget` (Forget / Keep it), "forget my face", or `kurooto face forget` (it asks; `--yes` doesn't);
- **Forget everything** on the Face page;
- **Delete my face data**, offered when you turn Face presence off (until then the model stays, and turning it on
  again uses it);
- `/forget all` (it says so in its question).

It deletes the key first, then the template and its status. With the key gone, any old copy of the template (a backup
of the state folder, a synced folder) can't be read by anyone. Then: "Forgot your face model: the key, the template
and its status. Nothing of it remains on this computer." Nothing went anywhere else, so there's nothing to forget
elsewhere.

## Privacy

- **What it sees:** the camera's picture, only while it looks (above), at about one frame a second (up to 5 while
  Voice listens for a look). With look to talk by your eyes, your eyes are cut from each frame in memory and turned into
  two numbers (where the irises sit), dropped with the frame.
- **What it keeps:** your template only: numbers that describe your face, never a picture, encrypted (AES-GCM) under a
  key in your system's keychain, in `state/face/template.bin`, with a status file of counts and dates. Calibrating
  your eyes adds four numbers to the same template. Never in a
  backup, Profile sync or a diagnostics bundle.
- **What it never keeps:** the camera's frames (looked at in memory and dropped), the preview (made in memory for the
  Face page), and anything of other people: a stranger's face is dropped with the frame, and only a count since start
  is kept ("faces: you 120, unsure 4, not you 9").
- **What leaves your computer:** nothing. The one-time downloads fetch the models from `media.githubusercontent.com`
  (OpenCV's model zoo), the package from PyPI and, only if you tap Get the eye model, MediaPipe's iris model from
  `storage.googleapis.com`; nothing of yours is sent.
- **Honest limits:** without a keychain (no keychain service, starting at boot on Linux, or `KUROOTO_HOME` set) the key
  sits in Kurooto's owner-only settings file on the same disk, so the encryption then only protects copies of the state
  folder made without the settings folder. Deleting a file on an SSD doesn't erase it, which is why forgetting deletes
  the key first. Python can't promise a frame is wiped from memory or never swapped to disk.

## It's not a lock

A face is easy to copy: a photo or video of you on a phone will usually pass, and a sibling or lookalike can be taken
for you (strict strictness helps; the "someone else" test shows it). Real liveness checks need a depth or infrared
camera, or asking you to blink or turn, which would make a greeting a chore. So the rule is: **a face match never
authorises anything.** It never answers an approval, unlocks your screen or Kurooto, or lets a spoken request do more
than it could anyway. The worst a photo of you can do is make Kurooto say good morning and open a conversation anyone in
the room could already open by saying "Kurooto".

One narrow exception, with Voice ID on (0.8.13, `voice.speaker_id.face_assist`, on by default): when Voice ID is only
"not sure" a voice is yours (its score just under the line, inside the margin) and Face presence sees exactly one face,
yours, that voice counts as you. A voice clearly not yours, two voices, two faces or strict strictness never do, and a
face with no voice never does anything. Turn `voice.speaker_id.face_assist` off if a photo of you plus a voice close to
yours is a risk where you live.

## Commands

| Command | What it does |
|---|---|
| `/face` | what it's doing, the model's grade, and the faces it saw since start (counts only) |
| `/face pause [1h\|30m\|off]` | no camera for that long (or until `/face pause off`) |
| `/face forget` | delete your face model (asks first) |
| "is the camera on?", "are you watching me?" | the same as `/face` |
| "stop watching", "pause the camera for an hour" | pause it |
| "forget my face" | asks, then forgets |

From a terminal: `kurooto face`, `kurooto face pause 1h`, `kurooto face forget [--yes]`,
`kurooto face install-from FOLDER`, `kurooto face test-camera`.

## Settings

| Setting | Default | What it does |
|---|---|---|
| `face.camera.device` | (the first) | which camera: a number or part of its name |
| `face.camera.yaw_offset_deg` | 0 | degrees beside the lens the spot to look at sits (+: your right); look to talk centres there |
| `face.watch.fps`, `fps_battery` | 1, 0.33 | frames a second while it looks |
| `face.watch.look_fps` | 5 | frames a second while Voice listens for a look (at most 5; 0: as usual) |
| `face.watch.idle_s` | 60 | seconds without input before it looks |
| `face.watch.when_locked`, `night` | off, off | also look while locked, at night |
| `face.recognise.strictness` | `normal` | `loose`, `normal` or `strict` (retrains) |
| `face.recognise.threshold` | 0 | a fixed threshold instead of the calibrated one (never below 0.363) |
| `face.recognise.min_face_px` | 60 | smaller faces are ignored (pixels of a 640x480 picture; scaled for a sharper camera) |
| `face.recognise.frames` | 3 | frames of 4 that must be you |
| `face.greet.on`, `talk` | on, on | the greeting, and the conversation after it |
| `face.greet.after_absent_min`, `gap_min`, `per_day` | 20, 60, 3 | when it greets |
| `face.greet.say` | next, waiting, deadline | what it mentions (`held` too) |
| `face.greet.with_others` | `skip` | `skip`, `short` or `full` |
| `face.away.on`, `hold_desktop`, `hold_calls` | off | noticing you left, and what waits |
| `face.learn.on`, `every_h`, `max`, `margin` | off, 6, 30, 0.08 | learning over time |
| `face.track.on`, `fps` | on, 10 | the being's eye follows every face in view, and how often it looks then |
| `face.addons.watch`, `hold` | on, on | let add-ons see who's in view, and keep the camera looking while you type |
| `voice.listen.need_face`, `face_near`, `face_yaw_deg` | on, 0.5, 35 | Voice answers only a face close and facing the camera ([Voice](voice.md#it-only-answers-someone-in-front-of-it)) |

All of them: [the settings guide](../../SETTINGS_GUIDE.md).

## Licences

- YuNet: MIT (Shiqi Yu). SFace: Apache-2.0. Both from OpenCV's model zoo, downloaded at setup, not part of Kurooto.
- The eye model (optional): MediaPipe Iris, `iris_landmark.tflite`, Apache-2.0 (Google), from MediaPipe's model store,
  downloaded only when you tap Get the eye model.
- opencv-python-headless: Apache-2.0. Its wheel bundles FFmpeg's libraries (LGPL-2.1+), OpenBLAS (BSD-3), libvpx
  (BSD), libpng, OpenSSL and the GCC runtime (GPL-3.0 with the runtime library exception). numpy: BSD-3.
- SFace's training data: OpenCV's page doesn't name it; the SFace paper reports training on public celebrity-face
  datasets (CASIA-WebFace, VGGFace2, MS-Celeb-1M variants), whose own terms are research-oriented. The weights are
  published under Apache-2.0; whether a dataset's terms reach a model trained on it is unsettled.

## Troubleshooting

| Problem | What to do |
|---|---|
| "no camera" | plug one in; on a laptop, check the privacy shutter or a hardware switch; `face.camera.device` if it picked the wrong one |
| "camera in use by another program" | close the video call or app using it; Kurooto tries again every minute and never forces it (Kurooto's own programs, such as an add-on feeding a phone's camera, never count) |
| "camera blocked by the system" | macOS: System Settings → Privacy & Security → Camera, allow Terminal (or Kurooto's launcher), or run `kurooto face test-camera` in a terminal once to get the question. Windows: Settings → Privacy & security → Camera → "Let desktop apps access your camera" |
| "camera covered" | open the shutter or the lid; it checks again every 5 minutes |
| It picked an infrared camera (grey picture, never recognises you) | set `face.camera.device` to your ordinary camera's number or name |
| Good frames rejected as blurry or dark | more light on your face; the limits are first guesses, so tell us |
| "weak model" | Add samples on the Face page, especially the steps the advice names, then Retrain |
| It took someone else (a lookalike) for you | set strictness to strict; retrain; remember it's never a lock |
| "re-enrol needed (the recognition model changed)" | a new release brought another model: enrol again (old samples can't be compared with it) |
| "template locked" | the keychain is locked (often right after boot); it waits and never makes a new key over your model |
| No greeting | `/face` says why it's paused; the greeting needs Voice on and speaking, no call, focus or night, and 20 minutes away |
| Voice ignores you ("no one facing it nearby") | face the camera when you talk; if you sit further back than usual, lower `voice.listen.face_near`; with a second screen beside you, raise `voice.listen.face_yaw_deg`; or turn `voice.listen.need_face` off |
| Looking at the camera doesn't open Voice (by your eyes) | the Face page shows your last look's angles while Voice listens: calibrate again in your usual light, raise `voice.listen.look_gaze_yaw_deg` / `look_gaze_pitch_deg`, or turn `voice.listen.look_gaze` off (glasses' reflections can hide the irises) |
| A video call app can't get the camera while Voice listens | `/voice mute` or `/face pause 1h` for the call, or turn `voice.listen.need_face` and `voice.listen.look_to_talk` off |

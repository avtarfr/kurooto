# What leaves your computer

Kurooto runs on your computer, and every feature is off until you turn it on. This page lists, per feature, exactly
what goes where. **Nothing is ever sent to Kurooto's author** (no analytics, no crash reports, no "phone home"). The
only things Kurooto fetches from its own release page are updates, checked against a signature.

Everything below goes to services you chose, under your own accounts.

## Always (when the feature is on)

| Feature | What leaves | Where to |
|---|---|---|
| Telegram | your messages to the bot and its replies; files you send it | Telegram (to your own bot) |
| Chat with your AI | what you ask; notes the AI reads to answer | the AI service you picked (Google for agy/Gemini, OpenAI for Codex, Anthropic for Claude Code, the service you entered for a custom one, or nothing for local models) |
| Files into notes | with Chat on, the files you send, for the AI to file them | the AI service you picked |
| Nightly look back | counts of what happened today (never your messages) and your settings' values | the AI service you picked |
| Notes brain (GBrain) | nothing on computers with a graphics card or Apple Silicon (the index is made locally); on others, note text, to make the index | Google (Gemini, your key), unless you chose keyword-only |
| Phone calls | call audio and what's said on calls; the call setup (your name, the assistant's name, which tools exist); for calls while the computer is off: a short brief (what's due, today's classes and check-ins, quiz questions) and your notes' titles, headings and first lines | Google (Gemini Live, your key); your own Cloudflare account (your call line) |
| Phone calls: ringing | "a call is ringing" messages, end-to-end encrypted (only your paired phones can read them) | ntfy.sh (Android) or Apple/Google push services (web app; the push itself is empty) |
| Morning alarm | the alarm time | your call line |
| Voice notes | the recordings | Google (Gemini, your key) |
| Calendar | nothing leaves; Kurooto reads your calendar's private link | (read from Google/Outlook/Apple) |
| Notes sync | your whole notes folder | your own private GitHub repository |
| Notes sync + Phone calls | read access to that repository, so calls can read notes while the computer is off | your call line (its secret store) |
| Google | Kurooto reads Classroom and writes drafts in your Gmail; nothing is sent from your Gmail | Google, with your own client and sign-in |
| Handwritten notes | the scans and photos | Google (Gemini, your key), unless a local vision model handles them |
| About you | the reports you add stay on this computer (Kurooto's data folder, not synced); building the profile sends them to the AI you picked, and its short "In brief" part goes along with every AI request | the AI service you picked |
| Research | your fields, keywords and searches (never your notes) | the sources you pick: arXiv, bioRxiv/medRxiv, PubMed, feeds (all public) |
| Local AI models, Reminders, Check-ins, Deadlines, Subjects, Quiz, Weekly summary, After-class notes, Study tracker, Stay awake on charger | nothing | stays on your computer |

## Free tiers and terms

**A free Gemini API key** (Google AI Studio's free tier):
- Google may use what you send and what it answers to improve its products, and human reviewers may read it.
- You must be 18 or older.
- In the EEA, the UK and Switzerland you need a paid key (billing turned on).
- Phone calls and voice notes always go through Gemini, whichever AI answers your messages.

If you don't want that, use a paid key: on paid tiers Google doesn't use what you send to improve its products. Or
keep those features off, or use local models where offered.

**Antigravity (agy):** Kurooto runs Google's official agy program on your computer, signed in as you, and never touches
its sign-in token. Google's answers differ on whether other tools may start agy unattended, so there is some risk to
your Google account. For tools like Kurooto, Google recommends a Gemini API key.

Every other AI service you pick (Codex, Claude Code, a custom OpenAI-compatible one) works under its own terms and your
own account. Kurooto no longer offers FreeLLMAPI, which pools other providers' free tiers; one set up with an earlier
version keeps working and shows as "Another OpenAI-compatible service".

## Secrets

Your bot token, keys, tokens and links are kept in your system's keychain (Windows Credential Manager, macOS Keychain,
the Secret Service on Linux), or, where there is none, in a file only your user can read. They're never written to
logs. `kurooto doctor --bundle` blanks them out (and names, addresses and folders) before saving anything.

## Your phone

The Android app keeps its pairing (the call line's address, its device key, the ring messages' key) in its private
storage. Nothing personal is built into the app. The iPhone web app keeps its device key in Safari's storage for the
Home Screen app. Unpair a phone with `/phones` → `/unpair`, or on the dashboard's Phone tab.

## Removing it all

`kurooto uninstall` removes Kurooto's settings and data from your computer (your notes folder is kept). Your call
line, Google client and notes repository are on your own accounts: delete them there (see the manual's Uninstall).

"""Every feature Kurooto has, in the order the wizard and Settings show them."""

from kurooto.modules.alarm import Alarm
from kurooto.modules.awake import Awake
from kurooto.modules.backups import Backups
from kurooto.modules.books import Books
from kurooto.modules.calendar import Calendar
from kurooto.modules.calls import Calls
from kurooto.modules.capture import Capture
from kurooto.modules.chat import Chat
from kurooto.modules.checkins import Checkins
from kurooto.modules.deadlines import Deadlines
from kurooto.modules.files import Files
from kurooto.modules.gbrain import GBrain
from kurooto.modules.google import Google
from kurooto.modules.google_calendar import GoogleCalendar
from kurooto.modules.google_classroom import ClassroomNotes
from kurooto.modules.google_drive import DriveUpload
from kurooto.modules.google_mail import DigestEmail, MailDigest, ReplyDrafts
from kurooto.modules.google_plan import AgentPlan
from kurooto.modules.handwritten import Handwritten
from kurooto.modules.library import Library
from kurooto.modules.local_models import LocalModels
from kurooto.modules.notes_sync import NotesSync
from kurooto.modules.overlay import AddOns
from kurooto.modules.profile import Profile
from kurooto.modules.quests import Quests
from kurooto.modules.quiz import Quiz
from kurooto.modules.remember import Remember
from kurooto.modules.reminders import Reminders
from kurooto.modules.research import Research
from kurooto.modules.retro import Retro
from kurooto.modules.skills import Skills
from kurooto.modules.study import Study
from kurooto.modules.subjects import Subjects
from kurooto.modules.telegram import Telegram
from kurooto.modules.terminal import KurootoTerminal
from kurooto.modules.terminals import Terminals
from kurooto.modules.voice_notes import VoiceNotes
from kurooto.modules.weekly import Weekly

CATALOG = [
    Telegram,
    Chat,
    Reminders,
    Checkins,
    Deadlines,
    Subjects,
    Quiz,
    Weekly,
    Quests,
    Files,
    Skills,
    Library,
    GBrain,
    LocalModels,
    Capture,
    Remember,
    Retro,
    Calls,
    Alarm,
    VoiceNotes,
    Awake,
    Calendar,
    NotesSync,
    Backups,
    Profile,
    Google,
    ClassroomNotes,
    MailDigest,
    ReplyDrafts,
    DigestEmail,
    AgentPlan,
    GoogleCalendar,
    DriveUpload,
    Handwritten,
    Books,
    Study,
    Research,
    Terminals,
    KurootoTerminal,
    AddOns,
]

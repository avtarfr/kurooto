"""Every feature Kurooto has, in the order the wizard and Settings show them."""

from kurooto.modules.alarm import Alarm
from kurooto.modules.awake import Awake
from kurooto.modules.backups import Backups
from kurooto.modules.books import Books
from kurooto.modules.calendar import Calendar
from kurooto.modules.calls import Calls
from kurooto.modules.capture import Capture
from kurooto.modules.cases import Cases
from kurooto.modules.chat import Chat
from kurooto.modules.checkins import Checkins
from kurooto.modules.classpacks import ClassPacks
from kurooto.modules.commitments import Commitments
from kurooto.modules.deadlines import Deadlines
from kurooto.modules.doubts import Doubts
from kurooto.modules.drafts import Drafts
from kurooto.modules.dreaming import Dreaming
from kurooto.modules.exam_season import ExamSeason
from kurooto.modules.files import Files
from kurooto.modules.finder import Finder
from kurooto.modules.gbrain import GBrain
from kurooto.modules.google import Google
from kurooto.modules.google_calendar import GoogleCalendar
from kurooto.modules.google_classroom import ClassroomNotes
from kurooto.modules.google_drive import DriveUpload
from kurooto.modules.google_mail import DigestEmail, MailDigest, ReplyDrafts
from kurooto.modules.google_plan import AgentPlan
from kurooto.modules.handwritten import Handwritten
from kurooto.modules.hints import Hints
from kurooto.modules.integrate import Integrate
from kurooto.modules.learning import Learning
from kurooto.modules.library import Library
from kurooto.modules.lidsafe import LidSafe
from kurooto.modules.local_models import LocalModels
from kurooto.modules.mind import Mind
from kurooto.modules.notes_sync import NotesSync
from kurooto.modules.overlay import AddOns
from kurooto.modules.profile import Profile
from kurooto.modules.projects import Projects
from kurooto.modules.quests import Quests
from kurooto.modules.quiz import Quiz
from kurooto.modules.remember import Remember
from kurooto.modules.reminders import Reminders
from kurooto.modules.research import Research
from kurooto.modules.research_addon import ResearchAddon
from kurooto.modules.retro import Retro
from kurooto.modules.skills import Skills
from kurooto.modules.sorter import Sorter
from kurooto.modules.space import Space
from kurooto.modules.startby import StartBy
from kurooto.modules.study import Study
from kurooto.modules.subjects import Subjects
from kurooto.modules.telegram import Telegram
from kurooto.modules.terminal import KurootoTerminal
from kurooto.modules.terminals import Terminals
from kurooto.modules.voice import Voice
from kurooto.modules.voice_notes import VoiceNotes
from kurooto.modules.weekly import Weekly

CATALOG = [
    Telegram,
    Chat,
    Reminders,
    Checkins,
    Deadlines,
    StartBy,
    Subjects,
    Commitments,
    ClassPacks,
    Doubts,
    Quiz,
    ExamSeason,
    Dreaming,
    Mind,
    Weekly,
    Quests,
    Files,
    Projects,
    Skills,
    Sorter,
    Finder,
    Hints,
    Drafts,
    Library,
    GBrain,
    LocalModels,
    Capture,
    Remember,
    Retro,
    Learning,
    Cases,
    Calls,
    Alarm,
    LidSafe,
    VoiceNotes,
    Voice,
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
    Integrate,
    Space,
    Study,
    Research,
    ResearchAddon,
    Terminals,
    KurootoTerminal,
    AddOns,
]

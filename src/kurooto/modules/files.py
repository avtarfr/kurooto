"""Files: photos, PDFs and documents you send land in your notes folder's inbox, or in your files folder's inbox when
you set one (files.folder: big files stay out of your notes and their history). With Chat on, the AI files them
properly (a note that describes and links the file, in the right place); the caption tells it what it's for."""

from __future__ import annotations

from kurooto.core import layout
from kurooto.modules.base import Incoming, Module


class Files(Module):
    id = "files"
    title = "Files into notes"
    description = "Send a photo or PDF on Telegram; it's saved to your notes, and filed by the AI if Chat is on."
    requires = ("telegram",)
    telegram_only = True  # what comes to your bot (the phone app shares files its own way)
    privacy = "Files are saved on this computer. With Chat on, the AI you picked reads them to file them."

    def take_files(self, msg: Incoming) -> str:
        rel = [layout.shown(self.app, f) for f in msg.files]
        self.app.events.emit("files_in", n=len(rel))
        if not self.app.is_on("chat"):
            return f"Saved to {', '.join(rel)}."
        caption = msg.text.strip()
        outside = layout.files_root(self.app) is not None  # files.folder: files stay out of the notes
        where = "outside the notes folder" if outside else "in the notes folder"
        tidy = (
            "where it is (never copy a file into the notes folder)"
            if outside
            else "(move the file next to that note if that's tidier)"
        )
        prompt = (
            f"These files were just sent and saved {where}: {', '.join(rel)}."
            + (f" The sender wrote: {caption}." if caption else "")
            + " File them sensibly: create or update a note in the right place that says what each file is "
            f"and links to it {tidy}, then reply with where it went in one line."
        )
        self.app.jobs.submit(prompt, title=f"File: {msg.files[0].name}", reply_to=msg.message_id, effort="medium")
        return "Saved; filing it into your notes…"

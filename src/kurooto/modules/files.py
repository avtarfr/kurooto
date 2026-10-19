"""Files: photos, PDFs and documents you send land in your notes folder's inbox. With Chat on, the AI files them
properly (a note that describes and links the file, in the right place); the caption tells it what it's for."""

from __future__ import annotations

from kurooto.modules.base import Incoming, Module


class Files(Module):
    id = "files"
    title = "Files into notes"
    description = "Send a photo or PDF on Telegram; it's saved to your notes, and filed by the AI if Chat is on."
    requires = ("telegram",)
    privacy = "Files are saved on this computer. With Chat on, the AI you picked reads them to file them."

    def take_files(self, msg: Incoming) -> str:
        rel = [f.relative_to(self.app.workspace).as_posix() for f in msg.files]
        self.app.events.emit("files_in", n=len(rel))
        if not self.app.is_on("chat"):
            return f"Saved to {', '.join(rel)}."
        caption = msg.text.strip()
        prompt = (
            f"These files were just sent and saved in the notes folder: {', '.join(rel)}."
            + (f" The sender wrote: {caption}." if caption else "")
            + " File them sensibly: create or update a note in the right place that says what each file is "
            "and links to it (move the file next to that note if that's tidier), then reply with where it "
            "went in one line."
        )
        self.app.jobs.submit(prompt, title=f"File: {msg.files[0].name}", reply_to=msg.message_id, effort="medium")
        return "Saved; filing it into your notes…"

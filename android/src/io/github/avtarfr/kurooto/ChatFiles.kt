package io.github.avtarfr.kurooto

import android.content.ContentResolver
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.media.MediaPlayer
import android.media.MediaRecorder
import android.net.Uri
import android.os.Build
import android.provider.OpenableColumns
import android.util.LruCache
import android.webkit.MimeTypeMap
import androidx.core.content.FileProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import org.json.JSONObject
import java.io.File
import java.net.URLEncoder
import java.security.MessageDigest
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Files in the chat (0.8.10), all off the main thread:
 *  - sending: the bytes go up first to your call line's /upload in 512 KB parts, as ShareActivity's do (kept in the
 *    phone outbox while your computer is off), with an id made here (the message's `file.fid`) and `chat=<session>`
 *    (so your computer keeps it for the chat instead of filing it); then the message refers to them (`voice: true` for
 *    a voice note). A copy stays in the app's files (chat-files/) so your own photo shows at once.
 *  - receiving: a file from your computer comes as the sealed call-line link ("f1": `<line>/file#i=…&k=…&n=…`, the key
 *    only in the #fragment). The app fetches `<line>/sealed/<i>` and opens it here (AES-256-GCM, nonce || ciphertext
 *    + tag), into the app's cache (chat/), never anywhere the key could leak to.
 *  - showing: photos decoded at the size they're drawn, kept in a small memory cache; opening and sharing through the
 *    app's FileProvider; voice notes recorded as AAC (.m4a) and played with MediaPlayer.
 */
object ChatFiles {
    private val bitmaps = object : LruCache<String, Bitmap>(24 * 1024 * 1024) {
        override fun sizeOf(key: String, value: Bitmap) = value.byteCount
    }

    fun authority(c: Context) = c.packageName + ".chatfiles"

    // ------------------------------------------------------------------------------------------- picking
    /** What a picked file is: its name, size and type (from the system's own answer). */
    class Picked(val uri: Uri, val name: String, val size: Long, val mime: String)

    fun describe(c: Context, uri: Uri): Picked {
        var name = "file"
        var size = -1L
        try {
            c.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { cur ->
                if (cur.moveToFirst()) {
                    cur.getString(0)?.let { name = it }
                    if (!cur.isNull(1)) size = cur.getLong(1)
                }
            }
        } catch (_: Exception) { }
        if (uri.scheme == ContentResolver.SCHEME_FILE) uri.path?.let { val f = File(it); name = f.name; size = f.length() }
        val mime = c.contentResolver.getType(uri)
            ?: MimeTypeMap.getSingleton().getMimeTypeFromExtension(name.substringAfterLast('.', "").lowercase())
            ?: "application/octet-stream"
        return Picked(uri, name, size, mime)
    }

    /** A place for the camera to write its photo (shared with the camera app through the FileProvider). */
    fun cameraTarget(c: Context): Uri {
        val d = File(c.cacheDir, "chat-cam").apply { mkdirs() }
        val f = File(d, "photo-" + System.currentTimeMillis() + ".jpg")
        return FileProvider.getUriForFile(c, authority(c), f)
    }

    // ------------------------------------------------------------------------------------------- sending
    /** Copy a picked file into the app (so it shows at once, and a failed send can be tried again), then upload it and
     *  send the message that carries it. Runs on Chat's IO thread, in order with everything else. */
    fun send(c: Context, session: String, p: Picked, caption: String, reply: String) {
        val app = c.applicationContext
        val id = Chat.newId()
        val fid = java.util.UUID.randomUUID().toString().replace("-", "")
        Chat.IO.execute {
            val local = try {
                val ext = p.name.substringAfterLast('.', "").take(8).filter { it.isLetterOrDigit() }
                val f = File(File(app.filesDir, "chat-files").apply { mkdirs() }, fid + if (ext.isEmpty()) "" else ".$ext")
                app.contentResolver.openInputStream(p.uri)!!.use { i -> f.outputStream().use { o -> i.copyTo(o) } }
                f
            } catch (e: Exception) {
                null
            }
            val size = local?.length() ?: p.size
            val file = JSONObject().put("fid", fid).put("name", p.name.take(120)).put("mime", p.mime).put("size", size)
                .put("path", local?.absolutePath ?: "")
            if (local == null) {
                Chat.put(app, mine(id, session, caption, reply, file).put("state", "failed").put("note", "Couldn't read that file."))
                return@execute
            }
            if (p.mime.startsWith("audio/") && p.name.startsWith("voice-")) file.put("voice", true)
            upload(app, id, session, caption, reply, file, local)
        }
    }

    private fun mine(id: String, session: String, text: String, reply: String, file: JSONObject): JSONObject {
        val m = JSONObject().put("id", id).put("from", "you").put("text", text).put("session", session)
            .put("at", System.currentTimeMillis() / 1000).put("file", file).put("state", "sending").put("note", "")
        if (reply.isNotEmpty()) m.put("re", reply)
        return m
    }

    /** Send a file message again (it failed): the upload, then the message. */
    fun resend(c: Context, m: ChatMsg) {
        val f = m.file ?: return
        val app = c.applicationContext
        Chat.IO.execute {
            val local = File(f.path)
            if (!local.isFile) { Chat.setState(app, m.id, "failed", "The file isn't on this phone any more."); return@execute }
            val file = JSONObject().put("fid", f.fid).put("name", f.name).put("mime", f.mime).put("size", f.size).put("path", f.path)
            if (f.audio && f.name.startsWith("voice-")) file.put("voice", true)
            upload(app, m.id, m.session, m.text, m.re, file, local)
        }
    }

    private fun upload(c: Context, id: String, session: String, caption: String, reply: String, file: JSONObject, local: File) {
        val m = Chat.find(c, id) ?: mine(id, session, caption, reply, file)
        Chat.put(c, m.put("state", "sending").put("note", ""))
        if (Chat.demo == null) {
            val why = put(c, file.optString("fid"), file.optString("name"), local.readBytes(), caption, session)
            if (why != null) { Chat.setState(c, id, "failed", why); return }
        }
        Chat.send(c, session, id, caption, reply, file)
    }

    /** The bytes to your call line's /upload, in parts, under this id: null when they're there (or waiting on the line
     *  for your computer), else why not. */
    private fun put(c: Context, fid: String, name: String, all: ByteArray, note: String, session: String): String? {
        if (ChatRules.tooBig(all.size.toLong())) return "It's ${ChatRules.size(all.size.toLong())}; the chat carries files up to 10 MB."
        val size = 512 * 1024
        val parts = maxOf(1, (all.size + size - 1) / size)
        for (p in 0 until parts) {
            val chunk = all.copyOfRange(p * size, minOf(all.size, (p + 1) * size))
            val url = Prefs.url(c) + "/upload?name=" + URLEncoder.encode(name, "UTF-8") + "&note=" + URLEncoder.encode(note.take(200), "UTF-8") +
                "&id=" + fid + "&part=" + p + "&parts=" + parts + "&chat=" + session
            val r = Net.request("POST", url, chunk, "application/octet-stream", Prefs.device(c), 120000)
            if (r.code == -1) return "Couldn't reach your call line. Is this phone online?"
            if (!r.ok()) {
                return try { JSONObject(r.body).let { it.optString("note", it.optString("error")) } } catch (_: Exception) { "" }
                    .ifEmpty { "The file didn't go through (${r.code})." }
            }
        }
        return null
    }

    // ------------------------------------------------------------------------------------------ receiving
    /** The file on this phone: your own copy, or the sealed one from your call line fetched and opened (cached).
     *  Null when it can't be had (gone after a day, offline, not ours). Off the main thread. */
    fun local(c: Context, f: ChatFile): File? {
        if (f.path.isNotEmpty() && File(f.path).isFile) return File(f.path)
        if (f.url.startsWith("demo:")) return demoFile(c, f)
        val link = ChatRules.f1(f.url) ?: return null
        val dir = File(c.cacheDir, "chat").apply { mkdirs() }
        val ext = f.name.substringAfterLast('.', "").take(8).filter { it.isLetterOrDigit() }
        val out = File(dir, sha(f.url).take(24) + if (ext.isEmpty()) "" else ".$ext")
        if (out.isFile && out.length() > 0) return out
        val blob = bytes(link[0]) ?: return null
        val plain = open(B64.decode(link[1]), blob) ?: return null
        val tmp = File(dir, out.name + ".part")
        tmp.writeBytes(plain)
        tmp.renameTo(out)
        return out
    }

    private fun bytes(url: String): ByteArray? {
        var con: java.net.HttpURLConnection? = null
        return try {
            con = java.net.URL(url).openConnection() as java.net.HttpURLConnection
            con.connectTimeout = 15000
            con.readTimeout = 60000
            if (con.responseCode !in 200..299) null else con.inputStream.use { Net.readAll(it) }
        } catch (_: Exception) {
            null
        } finally {
            con?.disconnect()
        }
    }

    /** f1: AES-256-GCM, the 12-byte nonce first, then the ciphertext and its tag (line.py seal_f1). */
    fun open(key: ByteArray, blob: ByteArray): ByteArray? = try {
        if (key.size != 32 || blob.size < 28) null
        else Cipher.getInstance("AES/GCM/NoPadding").run {
            init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, blob, 0, 12))
            doFinal(blob, 12, blob.size - 12)
        }
    } catch (_: Exception) {
        null
    }

    private fun sha(s: String): String = MessageDigest.getInstance("SHA-256").digest(s.toByteArray()).joinToString("") { "%02x".format(it) }

    /** A photo, decoded to about `width` pixels wide (cached). Off the main thread. */
    fun bitmap(c: Context, f: ChatFile, width: Int): Bitmap? {
        val key = (f.path.ifEmpty { f.url }) + "@" + width
        bitmaps.get(key)?.let { return it }
        val file = local(c, f) ?: return null
        val o = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.absolutePath, o)
        var sample = 1
        while (o.outWidth / (sample * 2) >= width) sample *= 2
        val b = BitmapFactory.decodeFile(file.absolutePath, BitmapFactory.Options().apply { inSampleSize = sample }) ?: return null
        bitmaps.put(key, b)
        return b
    }

    /** A content link to the file for another app (open, share). */
    fun uri(c: Context, file: File, name: String): Uri {
        // the name people see: a copy under its own name in the cache (the FileProvider shows the file's name)
        val dir = File(c.cacheDir, "chat-open").apply { mkdirs() }
        val safe = name.replace(Regex("[^\\w. ()-]"), "_").take(100).ifEmpty { "file" }
        val named = File(dir, safe)
        if (!named.isFile || named.length() != file.length()) file.copyTo(named, overwrite = true)
        return FileProvider.getUriForFile(c, authority(c), named)
    }

    fun openIntent(c: Context, file: File, f: ChatFile): Intent =
        Intent(Intent.ACTION_VIEW).setDataAndType(uri(c, file, f.name), f.mime).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)

    fun shareIntent(c: Context, file: File, f: ChatFile): Intent =
        Intent.createChooser(
            Intent(Intent.ACTION_SEND).setType(f.mime).putExtra(Intent.EXTRA_STREAM, uri(c, file, f.name)).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION),
            null,
        )

    /** Copy the file to where you chose (Save). */
    fun saveTo(c: Context, file: File, to: Uri): Boolean = try {
        c.contentResolver.openOutputStream(to)!!.use { o -> file.inputStream().use { it.copyTo(o) } }
        true
    } catch (_: Exception) {
        false
    }

    // ----------------------------------------------------------------------------------------- voice notes
    /** Hold the mic: records AAC into the cache until [stop] (the file) or [cancel]. */
    class Recorder(private val c: Context) {
        private var rec: MediaRecorder? = null
        private var file: File? = null
        var started = 0L
            private set

        fun start(): Boolean = try {
            val f = File(File(c.cacheDir, "chat-voice").apply { mkdirs() }, "voice-" + System.currentTimeMillis() + ".m4a")
            @Suppress("DEPRECATION")
            val r = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(c) else MediaRecorder()
            r.setAudioSource(MediaRecorder.AudioSource.MIC)
            r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            r.setAudioEncodingBitRate(64000)
            r.setAudioSamplingRate(44100)
            r.setOutputFile(f.absolutePath)
            r.prepare()
            r.start()
            rec = r
            file = f
            started = System.currentTimeMillis()
            true
        } catch (_: Exception) {
            release()
            false
        }

        /** The recording, or null if it was too short (under half a second) or failed. */
        fun stop(): File? {
            val f = file
            val long = System.currentTimeMillis() - started >= 500
            val ok = try { rec?.stop(); true } catch (_: Exception) { false }
            release()
            return if (ok && long && f != null && f.length() > 0) f else { f?.delete(); null }
        }

        fun cancel() {
            try { rec?.stop() } catch (_: Exception) { }
            release()
            file?.delete()
        }

        private fun release() {
            try { rec?.release() } catch (_: Exception) { }
            rec = null
        }
    }

    /** One voice note or audio file playing at a time. */
    object Player {
        private var mp: MediaPlayer? = null
        var playing by androidx.compose.runtime.mutableStateOf("")
            private set

        fun toggle(id: String, file: File) {
            if (playing == id) { stop(); return }
            stop()
            try {
                mp = MediaPlayer().apply {
                    setDataSource(file.absolutePath)
                    setOnCompletionListener { stop() }
                    prepare()
                    start()
                }
                playing = id
            } catch (_: Exception) {
                stop()
            }
        }

        fun stop() {
            try { mp?.release() } catch (_: Exception) { }
            mp = null
            playing = ""
        }

        fun position(): Float = try {
            mp?.let { if (it.duration > 0) it.currentPosition.toFloat() / it.duration else 0f } ?: 0f
        } catch (_: Exception) {
            0f
        }
    }

    // ------------------------------------------------------------------------------------------------ demo
    /** Demo files (debug and dev builds): a photo of a plot and a small PDF, drawn here, never fetched. */
    private fun demoFile(c: Context, f: ChatFile): File? {
        val dir = File(c.cacheDir, "chat-demo").apply { mkdirs() }
        val out = File(dir, f.name)
        if (out.isFile) return out
        return try {
            if (f.image) {
                val w = 960
                val h = 540
                val b = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
                val cv = Canvas(b)
                cv.drawColor(Color.rgb(240, 236, 224))
                val grid = Paint().apply { color = Color.rgb(170, 190, 205); strokeWidth = 2f }
                for (x in 0..w step 40) cv.drawLine(x.toFloat(), 0f, x.toFloat(), h.toFloat(), grid)
                for (y in 0..h step 40) cv.drawLine(0f, y.toFloat(), w.toFloat(), y.toFloat(), grid)
                val axis = Paint().apply { color = Color.rgb(40, 40, 40); strokeWidth = 4f }
                cv.drawLine(0f, h / 2f, w.toFloat(), h / 2f, axis)
                val pen = Paint().apply { color = Color.rgb(30, 70, 170); strokeWidth = 6f; style = Paint.Style.STROKE; isAntiAlias = true }
                val p = Path()
                for (x in 0 until w) {
                    var s = 0.0
                    val t = x / w.toDouble() * 4 * Math.PI
                    for (k in 1..29 step 2) s += Math.sin(k * t) / k
                    val y = h / 2f - (s * 4 / Math.PI * h * 0.32).toFloat()
                    if (x == 0) p.moveTo(0f, y) else p.lineTo(x.toFloat(), y)
                }
                cv.drawPath(p, pen)
                out.outputStream().use { b.compress(Bitmap.CompressFormat.JPEG, 88, it) }
            } else {
                val doc = android.graphics.pdf.PdfDocument()
                val page = doc.startPage(android.graphics.pdf.PdfDocument.PageInfo.Builder(595, 842, 1).create())
                page.canvas.drawText("Problem sheet 4 (made up for the demo)", 60f, 80f, Paint().apply { textSize = 18f })
                doc.finishPage(page)
                out.outputStream().use { doc.writeTo(it) }
                doc.close()
            }
            out
        } catch (_: Exception) {
            null
        }
    }
}

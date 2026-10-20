package io.github.avtarfr.kurooto;

/**
 * The parts of turn-by-turn calls (this phone's own speech recognition and voice, see CallActivity) that don't need
 * Android, so they're tested on the JVM (test/SpeechTest.java): calls into the call page, and the recognizer's errors.
 */
final class Speech {
    private Speech() { }

    /** window.kurootoSpeech.fn("arg") for the call page, the argument quoted so what was heard can't break out. */
    static String js(String fn, String arg) {
        return "window.kurootoSpeech&&window.kurootoSpeech." + fn + "(" + quote(arg) + ")";
    }

    /** A JavaScript string literal: quotes, backslashes, control and line-separator characters escaped, and the
     *  characters that matter in HTML too, so nothing in it ends the string or the script. */
    static String quote(String s) {
        if (s == null) return "\"\"";
        StringBuilder b = new StringBuilder(s.length() + 2).append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default:
                    if (c < 0x20 || c == '<' || c == '>' || c == '&' || c == '\'' || c == ' ' || c == ' ') {
                        b.append(String.format("\\u%04x", (int) c));
                    } else {
                        b.append(c);
                    }
            }
        }
        return b.append('"').toString();
    }

    /** SpeechRecognizer's error codes as the page knows them; it takes no-speech and no-match as nothing heard. */
    static String error(int code) {
        switch (code) {
            case 1: case 2: return "network";      // ERROR_NETWORK_TIMEOUT, ERROR_NETWORK
            case 3: return "audio";                 // ERROR_AUDIO
            case 4: case 11: return "server";       // ERROR_SERVER, ERROR_SERVER_DISCONNECTED
            case 5: return "stopped";               // ERROR_CLIENT (also when listening was stopped)
            case 6: return "no-speech";             // ERROR_SPEECH_TIMEOUT
            case 7: return "no-match";              // ERROR_NO_MATCH
            case 8: case 10: return "busy";         // ERROR_RECOGNIZER_BUSY, ERROR_TOO_MANY_REQUESTS
            case 9: return "permission";            // ERROR_INSUFFICIENT_PERMISSIONS
            case 12: case 13: return "language";    // ERROR_LANGUAGE_NOT_SUPPORTED, ERROR_LANGUAGE_UNAVAILABLE
            case 14: case 15: return "unavailable"; // ERROR_CANNOT_CHECK_SUPPORT, ..._LISTEN_TO_DOWNLOAD_EVENTS
            default: return "error";
        }
    }

    /** The on-device recognizer failed in a way the phone's speech service may not (its language isn't downloaded). */
    static boolean tryService(int code) {
        return code == 12 || code == 13 || code == 14 || code == 15;
    }
}

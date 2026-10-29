package io.github.avtarfr.kurooto;

import android.content.Context;

/**
 * One request to your computer over the call line (BeingRules' ops): sealed with this phone's chat key, marked live,
 * answered sealed for this phone. The being's page (ViewsPane) and, since 0.9.2, Today's Room card (op voice.room) use
 * it. Blocks: call it off the main thread. Returns the answer as a JSON object's text, with "ok" and "note" at least.
 */
final class BeingAsk {
    private BeingAsk() { }

    static String send(Context a, String op, String argsText) {
        if (!BeingRules.known(op)) return BeingRules.fail("Not something the phone asks.");
        String args = BeingRules.args(argsText);
        if (args == null) return BeingRules.fail("That request was too big.");
        if (!Prefs.paired(a)) return BeingRules.fail("This phone isn't paired with your computer.");
        byte[] key = Prefs.key(a);
        if (key.length == 0) return BeingRules.fail("This phone has no key: pair it again.");
        String id = Chat.newId();
        String sealed = Crypto.seal(key, BeingRules.fields(op, args, id, System.currentTimeMillis(), Chat.newId() + Chat.newId()));
        if (sealed == null) return BeingRules.fail("This phone has no key: pair it again.");
        Net.Reply r = Net.request("POST", Prefs.url(a) + "/chat", BeingRules.body(id, sealed).getBytes(Crypto.UTF8), "application/json", Prefs.device(a), 25000);
        return BeingRules.reply(r.code, r.body, (kind, token) -> {
            if ("k1".equals(kind)) return Crypto.open(Prefs.key(a), token);
            java.security.KeyPair k = Prefs.sealKeys(a);
            if (k == null) return null;
            return Seal.open(k.getPrivate(), ((java.security.interfaces.ECPublicKey) k.getPublic()).getParams(), token);
        });
    }
}

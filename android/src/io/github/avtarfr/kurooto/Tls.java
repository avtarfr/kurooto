package io.github.avtarfr.kurooto;

import android.content.Context;
import android.os.Build;

import java.io.InputStream;
import java.security.KeyStore;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;

import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.TrustManagerFactory;
import javax.net.ssl.X509TrustManager;

/** Android before 7.1.1 doesn't trust ISRG Root X1 (Let's Encrypt's root), and ntfy.sh's certificate chains to it.
 *  On those phones the app trusts the phone's own roots plus that one root (assets/isrgrootx1.der), for its own
 *  connections only. Newer phones are left alone. */
final class Tls {
    private Tls() { }

    static void install(Context c) {
        if (Build.VERSION.SDK_INT >= 25) return;
        try {
            KeyStore ks = KeyStore.getInstance(KeyStore.getDefaultType());
            ks.load(null, null);
            TrustManagerFactory sys = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
            sys.init((KeyStore) null);
            int i = 0;
            for (TrustManager tm : sys.getTrustManagers()) {
                if (tm instanceof X509TrustManager) {
                    for (X509Certificate cert : ((X509TrustManager) tm).getAcceptedIssuers()) ks.setCertificateEntry("sys" + i++, cert);
                }
            }
            InputStream in = c.getAssets().open("isrgrootx1.der");
            try {
                ks.setCertificateEntry("isrg-root-x1", CertificateFactory.getInstance("X.509").generateCertificate(in));
            } finally {
                in.close();
            }
            TrustManagerFactory tmf = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
            tmf.init(ks);
            SSLContext ctx = SSLContext.getInstance("TLS");
            ctx.init(null, tmf.getTrustManagers(), null);
            HttpsURLConnection.setDefaultSSLSocketFactory(ctx.getSocketFactory());
        } catch (Exception ignored) {
            // the phone's own trust store stays in charge
        }
    }
}

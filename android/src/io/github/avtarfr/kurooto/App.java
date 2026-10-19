package io.github.avtarfr.kurooto;

import android.app.Application;

public class App extends Application {
    @Override public void onCreate() {
        super.onCreate();
        Tls.install(this);
    }
}

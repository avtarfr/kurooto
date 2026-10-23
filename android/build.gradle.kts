// Kurooto's Android app, built by Gradle from 0.7.0 (screens in Jetpack Compose with Material 3 Expressive; services,
// receivers, calls, alarms, crypto, notifications and widgets stay plain framework Java). Run it through
// android/build.sh, which pins Gradle, computes the version and signs the APK:
//   android/build.sh          release (R8, unsigned from Gradle, signed by build.sh) -> build/kurooto(-debug).apk
//   android/build.sh --dev    the "dev" build: debuggable, io.github.avtarfr.kurooto.dev, "Kurooto dev", the demo extra
//   android/build.sh --lint   API-level lint (NewApi, InlinedApi) on the release variant
// Pinned (don't move without a reason): Gradle 8.14.6, AGP 8.13.2, Kotlin 2.3.21, Compose BOM 2026.06.01 (Compose
// 1.11.4), activity-compose 1.12.4, compileSdk 36. material3 is 1.5.0-alpha18, not the BOM's 1.4.0: 1.4.0 keeps the
// Expressive APIs (the expressive motion scheme, button groups, segmented list items, emphasized type) internal, and
// alpha18 is the newest material3 that still builds with compileSdk 36 and AGP 8 (alpha19 on needs compileSdk 37 and
// AGP 9.1, which aren't installed).
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application") version "8.13.2"
    id("org.jetbrains.kotlin.android") version "2.3.21"
    id("org.jetbrains.kotlin.plugin.compose") version "2.3.21"
}

android {
    namespace = "io.github.avtarfr.kurooto"
    compileSdk = 36

    defaultConfig {
        applicationId = "io.github.avtarfr.kurooto"
        minSdk = 23
        targetSdk = 35
        versionCode = (findProperty("kurootoVersionCode") as String? ?: "1").toInt()
        versionName = findProperty("kurootoVersionName") as String? ?: "0.0.0"
        manifestPlaceholders["appLabel"] = "Kurooto"
    }

    sourceSets["main"].apply {
        manifest.srcFile("AndroidManifest.xml")
        java.srcDirs("src")
        kotlin.srcDirs("src")
        res.srcDirs("res")
        assets.srcDirs("assets")
    }

    buildTypes {
        getByName("release") {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = null // build.sh signs it (the release keystore, or a debug key)
        }
        create("dev") {
            initWith(getByName("debug"))
            applicationIdSuffix = ".dev" // installs beside the real app
            versionNameSuffix = "-dev"
            manifestPlaceholders["appLabel"] = "Kurooto dev"
            signingConfig = null // build.sh signs it with its debug key
            matchingFallbacks += listOf("debug")
        }
    }

    // the "demo" intent extra (made-up Today, Inbox and checklist, no pairing): its sample data is only in debug and
    // dev builds (src-demo); release builds get src-nodemo, where Demo.ON is false and there's no sample data at all
    sourceSets["debug"].kotlin.srcDirs("src-demo")
    sourceSets["dev"].kotlin.srcDirs("src-demo")
    sourceSets["release"].kotlin.srcDirs("src-nodemo")

    buildFeatures {
        compose = true
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    androidResources {
        localeFilters += listOf("en") // the app is in English; the libraries' other languages only add size
    }
    lint {
        checkOnly += setOf("NewApi", "InlinedApi")
        abortOnError = true
        checkReleaseBuilds = false // build.sh --lint runs it (CI); a plain build stays quick and offline after the first
    }
    packaging {
        resources.excludes += setOf("/META-INF/{AL2.0,LGPL2.1}", "/META-INF/*.version", "DebugProbesKt.bin", "kotlin-tooling-metadata.json")
    }
    dependenciesInfo {
        includeInApk = false // no Google-signed dependency block in the APK
        includeInBundle = false
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
        optIn.add("androidx.compose.material3.ExperimentalMaterial3ExpressiveApi")
        optIn.add("androidx.compose.material3.ExperimentalMaterial3Api")
    }
}

dependencies {
    val bom = platform("androidx.compose:compose-bom:2026.06.01")
    implementation(bom)
    implementation("androidx.activity:activity-compose:1.12.4")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3:1.5.0-alpha18") // see the top of this file
}

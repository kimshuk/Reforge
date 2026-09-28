import java.net.URI

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
}

val backendUrlProperty = providers.gradleProperty("REFORGE_BACKEND_BASE_URL")
val debugBackendUrl = backendUrlProperty.orElse("http://10.0.2.2:3000")
val releaseBackendUrl = backendUrlProperty.orElse("")

fun String.asBuildConfigString(): String = buildString {
    append('"')
    for (character in this@asBuildConfigString) {
        when (character) {
            '\\' -> append("\\\\")
            '"' -> append("\\\"")
            '\n' -> append("\\n")
            '\r' -> append("\\r")
            else -> append(character)
        }
    }
    append('"')
}

val validateReleaseBackendUrl = tasks.register("validateReleaseBackendUrl") {
    doLast {
        val value = releaseBackendUrl.get().trim()
        val valid = runCatching { URI(value) }.getOrNull()?.let {
            it.scheme.equals("https", ignoreCase = true) &&
                !it.host.isNullOrBlank() &&
                it.port <= 65535 &&
                !value.contains("$(") &&
                !value.contains("${'$'}{") &&
                it.rawUserInfo == null &&
                it.rawQuery == null &&
                it.rawFragment == null
        } == true
        check(valid) { "Release requires REFORGE_BACKEND_BASE_URL to be an explicit HTTPS URL." }
    }
}

tasks.matching { it.name == "assembleRelease" || it.name == "bundleRelease" }
    .configureEach { dependsOn(validateReleaseBackendUrl) }

android {
    namespace = "com.andrewkim.reforge"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.andrewkim.reforge"
        minSdk = 26
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    buildTypes {
        getByName("debug") {
            buildConfigField("String", "BACKEND_BASE_URL", debugBackendUrl.get().asBuildConfigString())
            buildConfigField("boolean", "IS_RELEASE", "false")
        }
        getByName("release") {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            buildConfigField("String", "BACKEND_BASE_URL", releaseBackendUrl.get().asBuildConfigString())
            buildConfigField("boolean", "IS_RELEASE", "true")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    testOptions {
        unitTests.isIncludeAndroidResources = true
    }
}

ksp {
    arg("room.schemaLocation", "$projectDir/schemas")
}

dependencies {
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.material3)
    implementation(libs.compose.activity)
    implementation(libs.navigation.compose)
    implementation(libs.lifecycle.viewmodel.compose)
    implementation(libs.lifecycle.runtime.compose)
    implementation(libs.room.runtime)
    implementation(libs.room.ktx)
    ksp(libs.room.compiler)
    implementation(libs.retrofit)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.coil.compose)
    implementation(libs.coil.network.okhttp)
    implementation(libs.coroutines.android)
    implementation(libs.serialization.json)

    testImplementation(libs.junit)
    testImplementation(libs.coroutines.test)
    testImplementation(libs.mockwebserver)
    add("kspTestDebug", libs.room.compiler)

    androidTestImplementation(platform(libs.compose.bom))
    androidTestImplementation(libs.compose.ui.test.junit4)
    androidTestImplementation(libs.room.testing)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.rules)
    androidTestImplementation(libs.androidx.test.junit)
    androidTestImplementation(libs.espresso.core)
    debugImplementation(libs.compose.ui.tooling)
    debugImplementation(libs.compose.ui.test.manifest)
}

#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

backend_url="http://127.0.0.1:3000"
health_url="${backend_url}/health"
android_studio_java_home="/Applications/Android Studio.app/Contents/jbr/Contents/Home"

if ! command -v adb >/dev/null 2>&1; then
    printf 'adb was not found. Add Android SDK platform-tools to PATH.\n' >&2
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    printf 'curl was not found.\n' >&2
    exit 1
fi

if ! curl --fail --silent --show-error --max-time 5 "$health_url" >/dev/null; then
    printf 'Backend is not healthy at %s. Start Docker before running this script.\n' "$health_url" >&2
    exit 1
fi

emulator_serials=()
while IFS= read -r serial; do
    [[ -n "$serial" ]] && emulator_serials+=("$serial")
done < <(adb devices | awk '$2 == "device" && $1 ~ /^emulator-/ { print $1 }')

if [[ ${#emulator_serials[@]} -ne 1 ]]; then
    printf 'Expected exactly one running Android emulator, found %s.\n' "${#emulator_serials[@]}" >&2
    exit 1
fi

emulator_serial=${emulator_serials[0]}
adb -s "$emulator_serial" reverse tcp:3000 tcp:3000 >/dev/null

if [[ ! -x "${JAVA_HOME:-}/bin/java" ]]; then
    if [[ -x "$android_studio_java_home/bin/java" ]]; then
        export JAVA_HOME="$android_studio_java_home"
    else
        printf 'JAVA_HOME does not point to a JDK. Install JDK 17 or use Android Studio.\n' >&2
        exit 1
    fi
fi

./gradlew :app:assembleDebug \
    --console=plain \
    -PREFORGE_BACKEND_BASE_URL="$backend_url"

apk_path="app/build/outputs/apk/debug/app-debug.apk"
adb -s "$emulator_serial" install -r "$apk_path"
adb -s "$emulator_serial" shell am start -W \
    -n com.andrewkim.reforge/.MainActivity

printf 'Reforge is running on %s with backend %s.\n' "$emulator_serial" "$backend_url"

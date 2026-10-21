#!/usr/bin/env bash
# remoto/app/compilar.sh — compila la app del celular EN ESTA PC y deja el APK
# donde lo busca la ventana de la PC para instalarlo por cable.
#
#   remoto/app/compilar.sh            compila (la primera vez tarda: Gradle y el NDK)
#   remoto/app/compilar.sh --revisar  dice que falta, sin compilar
#
# Nunca en la nube de Expo (EAS): remoto/DISEÑO.md, «Solo Android, instalada
# por cable».
#
# LA FIRMA. Android solo deja actualizar una app con la MISMA firma con que se
# instalo. La clave vive fuera del repo (~/.config/celiuz/remoto/firma.keystore,
# con su contraseña al lado, 0600) y se crea la primera vez. Si se pierde, hay
# que desinstalar la app del celular y volver a emparejar.
#
# Se firma DESPUES de Gradle, con apksigner: asi no se toca android/, que lo
# genera Expo (`expo prebuild`) y no se versiona ni se edita a mano.
set -euo pipefail

APP="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
REMOTO="$(dirname "$APP")"
REVISAR=0
[ "${1:-}" = "--revisar" ] && REVISAR=1

rojo()  { printf '\033[31m%s\033[0m\n' "$*" >&2; }
verde() { printf '\033[32m%s\033[0m\n' "$*"; }
gris()  { printf '\033[90m%s\033[0m\n' "$*"; }

ruta() { python3 "$REMOTO/servidor/celiuz-remoto.py" rutas --json \
         | python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"; }
KEYSTORE="$(ruta firma_apk)"
CLAVE_KS="${KEYSTORE%.keystore}.clave"
DESTINO="$(ruta apk)"

# --- lo que hace falta --------------------------------------------------------
faltan=()
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
[ -d "$ANDROID_HOME/platforms" ] || faltan+=("el SDK de Android (no esta en $ANDROID_HOME; instala Android Studio o define ANDROID_HOME)")
if [ -z "${JAVA_HOME:-}" ]; then
    for j in /usr/lib/jvm/java-17-openjdk /usr/lib/jvm/default; do
        [ -x "$j/bin/java" ] && { export JAVA_HOME="$j"; break; }
    done
fi
[ -n "${JAVA_HOME:-}" ] && [ -x "$JAVA_HOME/bin/java" ] || faltan+=("Java 17 (sudo pacman -S jdk17-openjdk)")
command -v node >/dev/null || faltan+=("node y npm (sudo pacman -S nodejs npm)")
BUILD_TOOLS="$(ls -d "$ANDROID_HOME"/build-tools/* 2>/dev/null | sort -V | tail -1 || true)"
[ -x "$BUILD_TOOLS/apksigner" ] || faltan+=("apksigner (las build-tools del SDK de Android)")

if [ ${#faltan[@]} -gt 0 ]; then
    rojo "Falta:"
    printf '  - %s\n' "${faltan[@]}" >&2
    exit 1
fi
gris "  SDK:  $ANDROID_HOME"
gris "  Java: $JAVA_HOME"
gris "  APK:  $DESTINO"
if [ "$REVISAR" -eq 1 ]; then
    verde "No falta nada para compilar."
    exit 0
fi

# --- la clave de firma (una vez) ---------------------------------------------
if [ ! -f "$KEYSTORE" ]; then
    echo "Creando la clave de firma del APK (una sola vez)..."
    mkdir -p "$(dirname "$KEYSTORE")"
    chmod 700 "$(dirname "$KEYSTORE")"
    ( umask 077; python3 -c 'import secrets; print(secrets.token_urlsafe(24))' > "$CLAVE_KS" )
    "$JAVA_HOME/bin/keytool" -genkeypair -keystore "$KEYSTORE" -storetype PKCS12 \
        -alias celiuz-remoto -keyalg RSA -keysize 4096 -validity 36500 \
        -storepass:file "$CLAVE_KS" -dname "CN=Celiuz Remoto" >/dev/null 2>&1
    chmod 600 "$KEYSTORE"
    verde "  guardada en $KEYSTORE (si se pierde, hay que desinstalar la app y volver a emparejar)"
fi

# --- compilar ----------------------------------------------------------------
# Solo ARM: los celulares de verdad. x86 es para los emuladores y doblaba el
# APK (67 MB con las cuatro). armeabi-v7a se queda por los celulares viejos.
ARQUITECTURAS="${ARQUITECTURAS:-arm64-v8a,armeabi-v7a}"
cd "$APP"
[ -d node_modules ] || npm ci
# Las paginas de la terminal (xterm.js) y del escritorio remoto (noVNC) salen
# de node_modules: se rehacen siempre.
node scripts/gen-terminal.mjs
node scripts/gen-pantalla.mjs
echo "Generando el proyecto de Android (expo prebuild)..."
CI=1 EXPO_NO_GIT_STATUS=1 npx expo prebuild --platform android --clean --no-install >/dev/null
echo "Compilando (Gradle; la primera vez tarda varios minutos)..."
( cd android && ./gradlew --quiet assembleRelease -PreactNativeArchitectures="$ARQUITECTURAS" )
SIN_FIRMA="$APP/android/app/build/outputs/apk/release/app-release.apk"
[ -f "$SIN_FIRMA" ] || { rojo "Gradle no dejo el APK donde se esperaba: $SIN_FIRMA"; exit 1; }

echo "Firmando con la clave de esta PC..."
mkdir -p "$(dirname "$DESTINO")"
NUEVO="$(dirname "$DESTINO")/.celiuz-remoto.nuevo.apk"
"$BUILD_TOOLS/apksigner" sign --ks "$KEYSTORE" --ks-pass "file:$CLAVE_KS" \
    --ks-key-alias celiuz-remoto --out "$NUEVO" "$SIN_FIRMA"
"$BUILD_TOOLS/apksigner" verify "$NUEVO"
rm -f "$NUEVO.idsig"
mv -f "$NUEVO" "$DESTINO"
verde "Listo: $DESTINO ($(du -h "$DESTINO" | cut -f1))"
echo "Se instala desde la ventana de la PC (Celiuz Remoto -> Instalar la app), con el celular por cable."

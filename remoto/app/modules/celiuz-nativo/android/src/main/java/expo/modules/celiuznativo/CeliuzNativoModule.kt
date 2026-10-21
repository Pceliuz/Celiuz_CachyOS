// remoto/app/modules/celiuz-nativo — lo que Celiuz Remoto necesita de Android y
// ningun modulo de Expo daba junto.
//
// POR QUE EXISTE: en la primera version de la fase 6 lo bajado se quedaba en la
// carpeta privada de la app. «Abrir» se lo pasaba a otra app por un FileProvider,
// y eso no lo GUARDA en ningun sitio: Google Fotos enseñaba la foto pero no la
// tenia, el visor de documentos abria el .docx pero el archivo no aparecia en el
// explorador, y el video ni se reproducia. Lo que lo arregla es meterlo en
// MediaStore, que es la lista de archivos que ven todas las apps del celular:
//   imagen -> Pictures/Celiuz Remoto   (galeria, Google Fotos)
//   video  -> Movies/Celiuz Remoto     (galeria, Google Fotos)
//   audio  -> Music/Celiuz Remoto
//   resto  -> Download/Celiuz Remoto   (Archivos, Descargas)
// Desde Android 10 no pide ningun permiso: lo que una app mete en MediaStore es
// suyo. En Android 9 y antes no hay carpetas en MediaStore: se escribe en la
// carpeta publica (con WRITE_EXTERNAL_STORAGE, que pide la app) y se avisa al
// escaner de medios.
package expo.modules.celiuznativo

import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.media.MediaScannerConnection
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.webkit.MimeTypeMap
import expo.modules.kotlin.exception.Exceptions
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import java.io.File
import java.io.InputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

private const val SUBCARPETA = "Celiuz Remoto"

class CeliuzNativoModule : Module() {
  private val context: Context
    get() = appContext.reactContext ?: throw Exceptions.ReactContextLost()

  override fun definition() = ModuleDefinition {
    Name("CeliuzNativo")

    // origen: el file:// de lo bajado (en la cache de la app). sustituir: el
    // content:// de una copia anterior del MISMO archivo de la PC, para
    // «Bajar otra vez» sin dejar «nota (1).docx», «nota (2).docx»...
    AsyncFunction("guardarPublico") { origen: String, nombre: String, mime: String, sustituir: String? ->
      val entrada = abrirEntrada(origen)
      val tipo = mimeParaGuardar(nombre, mime)
      val (coleccion, carpeta) = destino(tipo)
      if (sustituir != null && existe(sustituir)) {
        val uri = Uri.parse(sustituir)
        entrada.use { e -> context.contentResolver.openOutputStream(uri, "wt")!!.use { e.copyTo(it, 256 * 1024) } }
        return@AsyncFunction mapOf("uri" to uri.toString(), "carpeta" to "$carpeta/$SUBCARPETA")
      }
      if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
        val valores = ContentValues().apply {
          put(MediaStore.MediaColumns.DISPLAY_NAME, nombre)
          put(MediaStore.MediaColumns.MIME_TYPE, tipo)
          put(MediaStore.MediaColumns.RELATIVE_PATH, "$carpeta/$SUBCARPETA")
          // A medias, nadie lo ve: la galeria no enseña un video cortado.
          put(MediaStore.MediaColumns.IS_PENDING, 1)
        }
        val resolver = context.contentResolver
        val uri = resolver.insert(coleccion!!, valores) ?: throw IllegalStateException("MediaStore no lo aceptó")
        try {
          entrada.use { e -> resolver.openOutputStream(uri, "w")!!.use { e.copyTo(it, 256 * 1024) } }
          resolver.update(uri, ContentValues().apply { put(MediaStore.MediaColumns.IS_PENDING, 0) }, null, null)
        } catch (ex: Exception) {
          resolver.delete(uri, null, null)
          throw ex
        }
        mapOf("uri" to uri.toString(), "carpeta" to "$carpeta/$SUBCARPETA")
      } else {
        @Suppress("DEPRECATION")
        val dir = File(Environment.getExternalStoragePublicDirectory(carpeta), SUBCARPETA)
        dir.mkdirs()
        val fichero = libre(dir, nombre)
        entrada.use { e -> fichero.outputStream().use { e.copyTo(it, 256 * 1024) } }
        mapOf("uri" to escanear(fichero, tipo).toString(), "carpeta" to "$carpeta/$SUBCARPETA")
      }
    }

    Function("existe") { uri: String -> existe(uri) }

    // Con la app que tenga el celular para ese tipo (la predeterminada, o el
    // selector de Android si hay varias). false si no hay NINGUNA: la app de
    // Celiuz Remoto ofrece entonces su visor o Compartir.
    AsyncFunction("abrir") { uri: String, mime: String ->
      val u = Uri.parse(uri)
      val tipos = listOfNotNull(mime, context.contentResolver.getType(u), "*/*").distinct()
      for (t in tipos) {
        val i = Intent(Intent.ACTION_VIEW).setDataAndType(u, t)
          .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        if (t != "*/*" && i.resolveActivity(context.packageManager) == null) continue
        if (t == "*/*") {
          // Ninguna app dice abrir ese tipo: el selector con «*/*» deja elegir
          // cualquiera, pero solo si hay alguna.
          if (context.packageManager.queryIntentActivities(i, 0).isEmpty()) return@AsyncFunction false
          context.startActivity(Intent.createChooser(i, null).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
          return@AsyncFunction true
        }
        context.startActivity(i)
        return@AsyncFunction true
      }
      false
    }

    AsyncFunction("compartir") { uri: String, mime: String, titulo: String ->
      val i = Intent(Intent.ACTION_SEND).setType(mime)
        .putExtra(Intent.EXTRA_STREAM, Uri.parse(uri))
        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
      context.startActivity(Intent.createChooser(i, titulo).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    AsyncFunction("borrar") { uri: String ->
      try {
        context.contentResolver.delete(Uri.parse(uri), null, null) > 0
      } catch (e: Exception) {
        false
      }
    }

    // Para el visor de texto de la app (un .md, un .txt, un .conf): no hace
    // falta tener ninguna app de markdown para leerlo.
    AsyncFunction("leerTexto") { uri: String, maximo: Int ->
      context.contentResolver.openInputStream(Uri.parse(uri))!!.use { e ->
        val buf = ByteArray(maximo)
        var n = 0
        while (n < maximo) {
          val r = e.read(buf, n, maximo - n)
          if (r < 0) break
          n += r
        }
        String(buf, 0, n, Charsets.UTF_8)
      }
    }
  }

  private fun abrirEntrada(origen: String): InputStream {
    val u = Uri.parse(origen)
    return if (u.scheme == null || u.scheme == "file") File(u.path ?: origen).inputStream()
    else context.contentResolver.openInputStream(u) ?: throw IllegalStateException("no puedo leer $origen")
  }

  // Lo que se le dice a MediaStore. Por la extension y no por lo que diga la
  // app: MediaStore puede cambiarle la extension al nombre si el tipo no casa
  // con ella. Con esto, en el HONOR un .md quedo «notas-prueba.md», tal cual
  // (medido el 2026-10-20).
  private fun mimeParaGuardar(nombre: String, mime: String): String {
    val ext = nombre.substringAfterLast('.', "").lowercase()
    return MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext)
      ?: if (mime.startsWith("image/") || mime.startsWith("video/") || mime.startsWith("audio/")) mime
      else "application/octet-stream"
  }

  private fun destino(tipo: String): Pair<Uri?, String> {
    val q = Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q
    return when {
      tipo.startsWith("image/") -> Pair(if (q) MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY) else null, Environment.DIRECTORY_PICTURES)
      tipo.startsWith("video/") -> Pair(if (q) MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY) else null, Environment.DIRECTORY_MOVIES)
      tipo.startsWith("audio/") -> Pair(if (q) MediaStore.Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY) else null, Environment.DIRECTORY_MUSIC)
      else -> Pair(if (q) MediaStore.Downloads.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY) else null, Environment.DIRECTORY_DOWNLOADS)
    }
  }

  private fun existe(uri: String): Boolean = try {
    context.contentResolver.query(Uri.parse(uri), arrayOf(MediaStore.MediaColumns._ID), null, null, null)
      ?.use { it.count > 0 } ?: false
  } catch (e: Exception) {
    false
  }

  private fun libre(dir: File, nombre: String): File {
    var f = File(dir, nombre)
    var n = 1
    val base = nombre.substringBeforeLast('.', nombre)
    val ext = if (nombre.contains('.')) "." + nombre.substringAfterLast('.') else ""
    while (f.exists()) f = File(dir, "$base ($n)$ext").also { n++ }
    return f
  }

  private fun escanear(f: File, tipo: String): Uri {
    var resultado: Uri? = null
    val listo = CountDownLatch(1)
    MediaScannerConnection.scanFile(context, arrayOf(f.absolutePath), arrayOf(tipo)) { _, uri ->
      resultado = uri
      listo.countDown()
    }
    listo.await(10, TimeUnit.SECONDS)
    return resultado ?: Uri.fromFile(f)
  }
}

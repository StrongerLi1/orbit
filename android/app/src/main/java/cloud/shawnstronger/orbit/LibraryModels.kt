package cloud.shawnstronger.orbit

import java.net.URI
import java.io.InputStream
import java.io.OutputStream
import java.nio.charset.StandardCharsets

data class LibraryBook(
    val id: String,
    val title: String,
    val author: String,
    val fileFormat: String,
    val originalFilename: String,
    val fileSize: Long,
    val hasCover: Boolean,
    val uploadedByName: String,
    val readerCount: Int,
    val readCount: Int,
    val currentUserReadCount: Int,
    val currentUserRead: Boolean,
    val canSendToKindle: Boolean,
    val createdAt: String,
    val updatedAt: String,
)

data class KindleSettings(
    val kindleEmail: String,
    val senderEmail: String,
    val enabled: Boolean,
    val maxAttachmentMb: Int,
)

data class LibraryRead(val id: String, val readDate: String, val createdAt: String, val updatedAt: String)
data class LibraryReader(val username: String, val isCurrentUser: Boolean, val reads: List<LibraryRead>)
data class LibraryReaders(val readerCount: Int, val readCount: Int, val readers: List<LibraryReader>)
data class LibraryReview(
    val id: String,
    val username: String,
    val content: String,
    val createdAt: String,
    val isAnonymous: Boolean,
    val canDelete: Boolean,
    val canToggleAnonymous: Boolean,
)

data class LibraryFilenameMetadata(val title: String, val author: String)

data class LibraryUploadFile(
    val filename: String,
    val contentType: String,
    val openStream: () -> InputStream,
)

internal class LatestLibraryRequest {
    private var generation = 0

    fun next(): Int = ++generation
    fun accepts(candidate: Int): Boolean = candidate == generation
    fun invalidate() { generation++ }
}

fun libraryMetadataFromFilename(filename: String): LibraryFilenameMetadata {
    val stem = filename.substringBeforeLast('.', filename).replace(Regex("\\s+"), " ").trim()
    if (stem.isBlank()) return LibraryFilenameMetadata("", "")
    Regex("^《(.+?)》(?:\\s*[-—–]\\s*|\\s+)(.+)$").matchEntire(stem)?.let {
        return LibraryFilenameMetadata(it.groupValues[1].trim(), it.groupValues[2].trim())
    }
    Regex("^(.+?)\\s+[-—–]\\s+(.+)$").matchEntire(stem)?.let {
        return LibraryFilenameMetadata(it.groupValues[1].trim(), it.groupValues[2].trim())
    }
    return LibraryFilenameMetadata(stem, "")
}

fun libraryBookExtension(filename: String): String = filename.substringAfterLast('.', "").lowercase()

fun isSupportedLibraryBook(filename: String): Boolean = libraryBookExtension(filename) in setOf("epub", "pdf", "mobi", "azw3", "txt")

fun libraryMimeType(format: String): String = when (format.lowercase()) {
    "epub" -> "application/epub+zip"
    "pdf" -> "application/pdf"
    "mobi", "azw3" -> "application/x-mobipocket-ebook"
    "txt" -> "text/plain"
    else -> "application/octet-stream"
}

fun formatLibraryFileSize(bytes: Long): String = when {
    bytes >= 1024L * 1024 -> "%.1f MB".format(bytes / (1024.0 * 1024.0))
    bytes >= 1024L -> "%.1f KB".format(bytes / 1024.0)
    else -> "$bytes B"
}

fun libraryShareUrl(origin: String, sharePath: String): String {
    val base = URI(origin)
    require(Regex("^/api/library/shares/(?:[A-HJ-KM-NP-Z2-9]{6}|[A-Za-z0-9_-]{43})/download$").matches(sharePath)) {
        "分享链接格式无效"
    }
    val resolved = base.resolve(sharePath)
    require(resolved.scheme == base.scheme && resolved.authority == base.authority) { "分享链接来源无效" }
    return resolved.toString()
}

internal fun writeLibraryMultipart(
    output: OutputStream,
    boundary: String,
    fields: Map<String, String>,
    files: Map<String, LibraryUploadFile>,
) {
    fun write(value: String) = output.write(value.toByteArray(StandardCharsets.UTF_8))
    fun token(value: String) = value.replace(Regex("[\\r\\n\"]"), "_")
    fields.forEach { (name, value) ->
        write("--$boundary\r\n")
        write("Content-Disposition: form-data; name=\"${token(name)}\"\r\n\r\n")
        write(value)
        write("\r\n")
    }
    files.forEach { (name, file) ->
        write("--$boundary\r\n")
        write("Content-Disposition: form-data; name=\"${token(name)}\"; filename=\"${token(file.filename)}\"\r\n")
        write("Content-Type: ${file.contentType.ifBlank { "application/octet-stream" }}\r\n\r\n")
        file.openStream().buffered().use { input -> input.copyTo(output, DEFAULT_BUFFER_SIZE) }
        write("\r\n")
    }
    write("--$boundary--\r\n")
}

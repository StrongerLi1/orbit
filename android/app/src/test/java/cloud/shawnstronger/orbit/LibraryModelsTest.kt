package cloud.shawnstronger.orbit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream

class LibraryModelsTest {
    @Test fun decodesCatalogReadersAndPrivacyProjections() {
        val book = OrbitJson.libraryBooks(
            """[{"id":"b1","title":"局外人","author":"加缪","fileFormat":"epub","originalFilename":"局外人.epub","fileSize":1234,"hasCover":true,"uploadedByName":"alice","readerCount":2,"readCount":3,"currentUserReadCount":2,"currentUserRead":true,"createdAt":"c","updatedAt":"u"}]""",
        ).single()
        assertEquals(1234L, book.fileSize)
        assertEquals(2, book.readerCount)
        assertTrue(book.currentUserRead)

        val readers = OrbitJson.libraryReaders(
            """{"readerCount":2,"readCount":3,"readers":[{"username":"alice","isCurrentUser":true,"reads":[{"id":"r1","readDate":"2026-10-14","createdAt":"c","updatedAt":"u"}]}]}""",
        )
        assertEquals("alice", readers.readers.single().username)
        assertTrue(readers.readers.single().isCurrentUser)
        assertEquals("2026-10-14", readers.readers.single().reads.single().readDate)
        assertTrue(OrbitJson.libraryReaders("{}").readers.isEmpty())

        val review = OrbitJson.libraryReviews(
            """[{"id":"v1","username":"匿名用户","content":"很好","createdAt":"c","isAnonymous":true,"canDelete":false,"canToggleAnonymous":false}]""",
        ).single()
        assertEquals("匿名用户", review.username)
        assertTrue(review.isAnonymous)
        assertFalse(review.canDelete)
        assertFalse(review.canToggleAnonymous)
        assertTrue(OrbitJson.libraryReviews("[]").isEmpty())
    }

    @Test fun filenamePreviewMatchesServerRules() {
        assertEquals(LibraryFilenameMetadata("局外人", "加缪"), libraryMetadataFromFilename("《局外人》 加缪.epub"))
        assertEquals(LibraryFilenameMetadata("The Myth", "Camus"), libraryMetadataFromFilename("The Myth - Camus.pdf"))
        assertEquals(LibraryFilenameMetadata("只有书名", ""), libraryMetadataFromFilename("只有书名.azw3"))
        assertEquals(LibraryFilenameMetadata("", ""), libraryMetadataFromFilename(""))
    }

    @Test fun fileAndShareHelpersStayWithinLibraryContract() {
        assertTrue(isSupportedLibraryBook("book.EPUB"))
        assertFalse(isSupportedLibraryBook("book.exe"))
        assertEquals("application/pdf", libraryMimeType("pdf"))
        assertEquals("1.5 KB", formatLibraryFileSize(1536))
        assertEquals("/api/library/shares/ABC234/download", OrbitJson.libraryShare("""{"sharePath":"/api/library/shares/ABC234/download"}"""))
        assertEquals(
            "https://orbit.example.com/api/library/shares/ABC234/download",
            libraryShareUrl("https://orbit.example.com", "/api/library/shares/ABC234/download"),
        )
        assertThrows(IllegalArgumentException::class.java) {
            libraryShareUrl("https://orbit.example.com", "https://evil.example/download")
        }
        assertThrows(IllegalArgumentException::class.java) {
            libraryShareUrl("https://orbit.example.com", "/api/library/shares/../../evil/download")
        }
    }

    @Test fun multipartFramingReopensFileStreamsForEveryAttempt() {
        var opens = 0
        val file = LibraryUploadFile("book.epub", "application/epub+zip") {
            opens++
            ByteArrayInputStream("ebook".toByteArray())
        }
        repeat(2) {
            val output = ByteArrayOutputStream()
            writeLibraryMultipart(output, "boundary", mapOf("title" to "书名"), mapOf("bookFile" to file))
            val body = output.toString(Charsets.UTF_8.name())
            assertTrue(body.contains("name=\"title\""))
            assertTrue(body.contains("filename=\"book.epub\""))
            assertTrue(body.contains("ebook"))
            assertTrue(body.endsWith("--boundary--\r\n"))
        }
        assertEquals(2, opens)
    }

    @Test fun onlyLatestCatalogRequestMayPublish() {
        val requests = LatestLibraryRequest()
        val older = requests.next()
        val latest = requests.next()
        assertFalse(requests.accepts(older))
        assertTrue(requests.accepts(latest))
        requests.invalidate()
        assertFalse(requests.accepts(latest))
    }
}

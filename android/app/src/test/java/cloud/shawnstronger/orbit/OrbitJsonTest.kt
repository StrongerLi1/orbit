package cloud.shawnstronger.orbit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.Assert.assertThrows
import kotlinx.coroutines.runBlocking
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId

class OrbitJsonTest {
    @Test fun kindleSettingsAndCatalogCapabilityDecode() {
        val settings = OrbitJson.kindleSettings(
            """{"kindleEmail":"reader@kindle.com","senderEmail":"books@example.com","enabled":true,"maxAttachmentMb":25}""",
        )
        assertEquals("reader@kindle.com", settings.kindleEmail)
        assertTrue(settings.enabled)
        assertEquals(25, settings.maxAttachmentMb)

        val book = OrbitJson.libraryBooks(
            """[{"id":"b1","title":"书名","author":"作者","fileFormat":"epub","originalFilename":"book.epub","fileSize":12,"hasCover":false,"uploadedByName":"alice","readerCount":0,"readCount":0,"currentUserReadCount":0,"currentUserRead":false,"canSendToKindle":true,"createdAt":"c","updatedAt":"u"}]""",
        ).single()
        assertTrue(book.canSendToKindle)
    }

    @Test fun todoLabelsAndLegacyTodosDecode() {
        val labels = OrbitJson.todoLabels("""[{"id":"label-1","name":"工作","createdAt":"now"}]""")
        assertEquals("工作", labels.single().name)
        val todos = OrbitJson.todos("""[{"id":"a","title":"已分类","priority":"high","dueDate":"","completed":false,"createdAt":"now","labelId":"label-1"},{"id":"b","title":"旧待办","priority":"medium","dueDate":"","completed":false,"createdAt":"then"}]""")
        assertEquals("label-1", todos[0].labelId)
        assertEquals(null, todos[1].labelId)
    }

    @Test fun permissionsComeFromServerPayload() {
        val user = OrbitJson.user(
            """{"id":"u","username":"reader","roles":["user"],"permissions":["content:read","hermes:chat"]}""",
        )
        assertTrue(user.can("content:read"))
        assertTrue(user.can("hermes:chat"))
        assertFalse(user.can("users:manage"))
    }

    @Test fun netdiskDecoderKeepsNormalizedMetadata() {
        val result = OrbitJson.netdisk(
            """{"keyword":"book","source":"PanSou","results":[{"title":"A","url":"https://example.com/a","source":"aliyun","description":"d","size":"1G","time":"today"}]}""",
        )
        assertEquals("book", result.keyword)
        assertEquals("aliyun", result.results.single().source)
        assertEquals("1G", result.results.single().size)
    }

    @Test fun diaryDecodersKeepServerPrivacyAndNestedFields() {
        val writing = OrbitJson.writings(
            """[{"id":"w1","content":"秘密","visibility":"private","isAnonymous":true,"createdAt":"c","updatedAt":"u","createdByName":"alice","isOwn":true,"canManage":true}]""",
        ).single()
        assertEquals("private", writing.visibility)
        assertEquals("alice", writing.createdByName)
        assertTrue(writing.isAnonymous)
        assertTrue(writing.canManage)

        val roll = OrbitJson.filmRolls(
            """[{"id":"r1","filmStock":"Gold 200","iso":null,"camera":"FM2","status":"active","createdAt":"c","updatedAt":"u","exposures":[{"id":"e1","rollId":"r1","frameNumber":2,"takenAt":"2026-10-12T02:30:00Z","location":"上海","thoughts":"光很好","lens":"50mm","aperture":"f/5.6","shutterSpeed":"1/250s","createdAt":"c","updatedAt":"u"}]}]""",
        ).single()
        assertEquals(null, roll.iso)
        assertEquals("Gold 200", roll.filmStock)
        assertEquals(2, roll.exposures.single().frameNumber)
        assertEquals("1/250s", roll.exposures.single().shutterSpeed)
    }

    @Test fun filmTimeAndNextFrameRoundTrip() {
        val zone = ZoneId.of("Asia/Shanghai")
        assertEquals(
            LocalDateTime.of(2026, 10, 12, 10, 30),
            filmLocalDateTime("2026-10-12T02:30:00Z", zone),
        )
        assertEquals(
            "2026-10-12T02:30:00Z",
            filmInstant(LocalDate.of(2026, 10, 12), LocalTime.of(10, 30), zone),
        )
        val exposure = FilmExposure("e", "r", 2, "", "", "", "", "", "", "", "")
        assertEquals(3, nextFilmFrame(listOf(exposure, exposure.copy(id = "e2"))))
        assertEquals(1, nextFilmFrame(emptyList()))
    }

    @Test fun serverOriginAllowsDefaultAndRequiresHttpsForOverrides() {
        val defaultOrigin = "https://shawnstronger.cloud"
        assertEquals(defaultOrigin, ServerOriginPolicy.resolve(null, defaultOrigin))
        assertEquals(defaultOrigin, ServerOriginPolicy.resolve("$defaultOrigin/", defaultOrigin))
        assertEquals("https://orbit.example.com:8443", ServerOriginPolicy.resolve(" https://orbit.example.com:8443/ ", defaultOrigin))
        assertThrows(IllegalArgumentException::class.java) { ServerOriginPolicy.resolve("http://orbit.example.com", defaultOrigin) }
        assertThrows(IllegalArgumentException::class.java) { ServerOriginPolicy.resolve("https://orbit.example.com/path", defaultOrigin) }
    }

    @Test fun contentSectionsContinueAfterOneEndpointFails() = runBlocking {
        val loaded = mutableListOf<String>()
        val failures = loadContentSections(
            listOf(
                "收藏" to suspend { loaded += "收藏" },
                "待办" to suspend { throw OrbitHttpException(500, "数据库忙") },
                "计划" to suspend { loaded += "计划" },
                "写点什么" to suspend { loaded += "写点什么" },
                "胶片日记" to suspend { loaded += "胶片日记" },
            ),
        )
        assertEquals(listOf("收藏", "计划", "写点什么", "胶片日记"), loaded)
        assertEquals(listOf(ContentSectionFailure("待办", "数据库忙")), failures)
    }

    @Test fun cookiesAreDiscardedWhenBackendOriginChanges() {
        assertTrue(shouldDiscardCookies(null, "https://shawnstronger.cloud"))
        assertTrue(shouldDiscardCookies("http://123.56.29.242", "https://shawnstronger.cloud"))
        assertFalse(shouldDiscardCookies("https://shawnstronger.cloud", "https://shawnstronger.cloud"))
    }
}

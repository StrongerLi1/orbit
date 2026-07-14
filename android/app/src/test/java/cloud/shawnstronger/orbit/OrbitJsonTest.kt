package cloud.shawnstronger.orbit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.Assert.assertThrows
import kotlinx.coroutines.runBlocking

class OrbitJsonTest {
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
            ),
        )
        assertEquals(listOf("收藏", "计划"), loaded)
        assertEquals(listOf(ContentSectionFailure("待办", "数据库忙")), failures)
    }

    @Test fun cookiesAreDiscardedWhenBackendOriginChanges() {
        assertTrue(shouldDiscardCookies(null, "https://shawnstronger.cloud"))
        assertTrue(shouldDiscardCookies("http://123.56.29.242", "https://shawnstronger.cloud"))
        assertFalse(shouldDiscardCookies("https://shawnstronger.cloud", "https://shawnstronger.cloud"))
    }
}

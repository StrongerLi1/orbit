package cloud.shawnstronger.orbit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SseParserTest {
    @Test fun preservesEventsSplitAcrossNetworkChunks() {
        val parser = SseParser()
        assertEquals(emptyList<SseEvent>(), parser.feed("event: delta\ndata: {\"content\":\"你"))
        val first = parser.feed("好\"}\n\nevent: completed\r\n")
        assertEquals(listOf(SseEvent("delta", "{\"content\":\"你好\"}")), first)
        val second = parser.feed("data: {\"ok\":true}\r\n\r\n")
        assertEquals(listOf(SseEvent("completed", "{\"ok\":true}")), second)
    }

    @Test fun ignoresKeepAliveComments() {
        val parser = SseParser()
        assertEquals(emptyList<SseEvent>(), parser.feed(": keep-alive\n\n"))
    }

    @Test fun joinsMultipleDataLinesWithoutReordering() {
        val parser = SseParser()
        assertEquals(
            listOf(SseEvent("delta", "first\nsecond")),
            parser.feed("event: delta\ndata: first\ndata: second\n\n"),
        )
    }

    @Test fun decodesHermesLifecycleEvents() {
        val started = OrbitJson.hermesStream(
            SseEvent("started", """{"conversation":{"id":"c"},"userMessage":{"id":"m","role":"user","content":"hi"}}"""),
        )
        val delta = OrbitJson.hermesStream(SseEvent("delta", """{"content":"你好"}"""))
        val failed = OrbitJson.hermesStream(SseEvent("error", """{"detail":"boom"}"""))
        assertTrue(started is HermesStreamEvent.Started)
        assertEquals(HermesStreamEvent.Delta("你好"), delta)
        assertEquals(HermesStreamEvent.Failed("boom"), failed)
    }

    @Test fun streamedTextStaysWithItsOriginConversation() {
        val projection = HermesStreamProjection("conversation-a").append("第一段").append("第二段")
        assertEquals("第一段第二段", projection.textFor("conversation-a"))
        assertEquals("", projection.textFor("conversation-b"))
    }
}

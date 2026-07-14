package cloud.shawnstronger.orbit

import org.json.JSONArray
import org.json.JSONObject
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.temporal.TemporalAdjusters
import java.net.URI

data class OrbitUser(
    val id: String,
    val username: String,
    val isAdmin: Boolean,
    val isBanned: Boolean,
    val roles: List<String>,
    val permissions: List<String>,
    val createdAt: String,
    val lastLoginAt: String,
) {
    fun can(permission: String) = permission in permissions
}

data class Folder(val id: String, val name: String, val sortOrder: Int, val createdAt: String)
data class Bookmark(
    val id: String,
    val title: String,
    val url: String,
    val category: String,
    val note: String,
    val favorite: Boolean,
    val createdAt: String,
)
data class Todo(
    val id: String,
    val title: String,
    val priority: String,
    val dueDate: String,
    val completed: Boolean,
    val createdAt: String,
)
data class Plan(
    val id: String,
    val title: String,
    val frequencyType: String,
    val targetCount: Int,
    val startDate: String,
    val endDate: String,
    val completions: Map<String, Int>,
    val time: String,
    val duration: Int,
    val color: String,
    val createdAt: String,
)
data class Excerpt(
    val id: String,
    val content: String,
    val source: String,
    val author: String,
    val excerptDate: String,
    val note: String,
    val createdAt: String,
)
data class ContentBundle(
    val bookmarks: List<Bookmark>,
    val todos: List<Todo>,
    val plans: List<Plan>,
    val folders: List<Folder>,
    val excerpts: List<Excerpt>,
)

data class ContentSectionFailure(val label: String, val detail: String)

suspend fun loadContentSections(sections: List<Pair<String, suspend () -> Unit>>): List<ContentSectionFailure> {
    val failures = mutableListOf<ContentSectionFailure>()
    sections.forEach { (label, load) ->
        try {
            load()
        } catch (failure: OrbitHttpException) {
            if (failure.status == 401) throw failure
            failures += ContentSectionFailure(label, failure.message ?: "请求失败")
        } catch (failure: Exception) {
            failures += ContentSectionFailure(label, failure.message ?: "暂时连接不上服务器")
        }
    }
    return failures
}

object ServerOriginPolicy {
    fun resolve(value: String?, defaultOrigin: String): String {
        val candidate = value?.trim()?.trimEnd('/').orEmpty()
        if (candidate.isBlank()) return defaultOrigin
        val uri = runCatching { URI(candidate) }.getOrElse { throw IllegalArgumentException("服务器地址格式无效") }
        require(uri.host != null && uri.path.orEmpty() in listOf("", "/") && uri.query == null && uri.fragment == null) {
            "服务器地址只能包含协议、主机和端口"
        }
        require(uri.scheme == "https" || candidate == defaultOrigin) { "自定义服务器必须使用 HTTPS" }
        return candidate
    }
}

fun shouldDiscardCookies(cookieOrigin: String?, activeOrigin: String): Boolean = cookieOrigin != activeOrigin

data class NetdiskResult(
    val title: String,
    val url: String,
    val source: String,
    val description: String,
    val size: String,
    val time: String,
)
data class NetdiskSearch(val keyword: String, val source: String, val results: List<NetdiskResult>)

data class HermesMessage(
    val id: String,
    val role: String,
    val content: String,
    val status: String,
    val createdAt: String,
)
data class HermesConversation(
    val id: String,
    val userId: String,
    val username: String,
    val title: String,
    val createdAt: String,
    val updatedAt: String,
    val messages: List<HermesMessage> = emptyList(),
    val generating: Boolean = false,
)
data class OrbitRole(val name: String, val description: String, val permissions: List<String>)
data class PermissionInfo(val name: String, val description: String)
data class AdminUser(
    val id: String,
    val username: String,
    val isAdmin: Boolean,
    val isBanned: Boolean,
    val roles: List<String>,
    val permissions: List<String>,
    val lastLoginAt: String,
)
data class HermesStatus(
    val configured: Boolean,
    val installed: Boolean,
    val running: Boolean,
    val dashboardUrl: String,
    val dashboardPublicUrl: String,
    val message: String,
    val details: String,
)

object OrbitJson {
    fun user(raw: String) = user(JSONObject(raw))
    fun user(obj: JSONObject) = OrbitUser(
        id = obj.text("id"),
        username = obj.text("username"),
        isAdmin = obj.optBoolean("isAdmin"),
        isBanned = obj.optBoolean("isBanned"),
        roles = obj.optJSONArray("roles").strings(),
        permissions = obj.optJSONArray("permissions").strings(),
        createdAt = obj.text("createdAt"),
        lastLoginAt = obj.text("lastLoginAt"),
    )

    fun folders(raw: String) = JSONArray(raw).objects(::folder)
    fun folder(obj: JSONObject) = Folder(obj.text("id"), obj.text("name"), obj.optInt("sortOrder"), obj.text("createdAt"))

    fun bookmarks(raw: String) = JSONArray(raw).objects(::bookmark)
    fun bookmark(obj: JSONObject) = Bookmark(
        obj.text("id"), obj.text("title"), obj.text("url"), obj.text("category"),
        obj.text("note"), obj.optBoolean("favorite"), obj.text("createdAt"),
    )

    fun todos(raw: String) = JSONArray(raw).objects(::todo)
    fun todo(obj: JSONObject) = Todo(
        obj.text("id"), obj.text("title"), obj.text("priority"), obj.text("dueDate"),
        obj.optBoolean("completed"), obj.text("createdAt"),
    )

    fun plans(raw: String) = JSONArray(raw).objects(::plan)
    fun plan(obj: JSONObject): Plan {
        val completions = mutableMapOf<String, Int>()
        obj.optJSONObject("completions")?.let { values ->
            values.keys().forEach { key -> completions[key] = values.optInt(key) }
        }
        return Plan(
            obj.text("id"), obj.text("title"), obj.text("frequencyType", "daily"),
            obj.optInt("targetCount", 1), obj.text("startDate"), obj.text("endDate"),
            completions, obj.text("time"), obj.optInt("duration", 30),
            obj.text("color", "violet"), obj.text("createdAt"),
        )
    }

    fun excerpts(raw: String) = JSONArray(raw).objects(::excerpt)
    fun excerpt(obj: JSONObject) = Excerpt(
        obj.text("id"), obj.text("content"), obj.text("source"), obj.text("author"),
        obj.text("excerptDate"), obj.text("note"), obj.text("createdAt"),
    )

    fun netdisk(raw: String): NetdiskSearch {
        val obj = JSONObject(raw)
        val results = obj.optJSONArray("results").objects { item ->
            NetdiskResult(
                item.text("title"), item.text("url"), item.text("source"), item.text("description"),
                item.text("size"), item.text("time"),
            )
        }
        return NetdiskSearch(obj.text("keyword"), obj.text("source"), results)
    }

    fun conversations(raw: String) = JSONArray(raw).objects(::conversation)
    fun conversation(raw: String) = conversation(JSONObject(raw))
    fun conversation(obj: JSONObject) = HermesConversation(
        id = obj.text("id"), userId = obj.text("userId"), username = obj.text("username"),
        title = obj.text("title"), createdAt = obj.text("createdAt"), updatedAt = obj.text("updatedAt"),
        messages = obj.optJSONArray("messages").objects(::message),
        generating = obj.optBoolean("generating"),
    )
    fun message(obj: JSONObject) = HermesMessage(
        obj.text("id"), obj.text("role"), obj.text("content"), obj.text("status", "completed"), obj.text("createdAt"),
    )

    fun adminUsers(raw: String) = JSONArray(raw).objects { obj ->
        AdminUser(
            obj.text("id"), obj.text("username"), obj.optBoolean("isAdmin"), obj.optBoolean("isBanned"),
            obj.optJSONArray("roles").strings(), obj.optJSONArray("permissions").strings(), obj.text("lastLoginAt"),
        )
    }
    fun roles(raw: String) = JSONArray(raw).objects { obj ->
        OrbitRole(obj.text("name"), obj.text("description"), obj.optJSONArray("permissions").strings())
    }
    fun permissions(raw: String) = JSONArray(raw).objects { obj -> PermissionInfo(obj.text("name"), obj.text("description")) }
    fun hermesStatus(raw: String): HermesStatus {
        val obj = JSONObject(raw)
        return HermesStatus(
            obj.optBoolean("configured"), obj.optBoolean("installed"), obj.optBoolean("running"),
            obj.text("dashboardUrl"), obj.text("dashboardPublicUrl", "/hermes-dashboard/"),
            obj.text("message"), obj.text("details"),
        )
    }

    private fun JSONObject.text(name: String, fallback: String = ""): String =
        if (isNull(name)) fallback else optString(name, fallback)

    private fun JSONArray?.strings(): List<String> =
        if (this == null) emptyList() else List(length()) { index -> optString(index) }.filter { it.isNotBlank() }

    private fun <T> JSONArray?.objects(decode: (JSONObject) -> T): List<T> =
        if (this == null) emptyList() else List(length()) { index -> decode(optJSONObject(index) ?: JSONObject()) }
}

data class PlanProgress(val done: Int, val target: Int)
data class PlanHistory(val periods: Int, val successful: Int, val totalExecutions: Int)

object PlanMath {
    fun isActive(plan: Plan, date: LocalDate): Boolean {
        val start = LocalDate.parse(plan.startDate)
        val end = plan.endDate.takeIf(String::isNotBlank)?.let(LocalDate::parse)
        return !date.isBefore(start) && (end == null || !date.isAfter(end))
    }

    fun periodKey(plan: Plan, date: LocalDate): String = when (plan.frequencyType) {
        "weekly" -> "week:${date.with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY))}"
        "monthly" -> "month:${date.toString().take(7)}"
        else -> "day:$date"
    }

    fun countInPeriod(plan: Plan, date: LocalDate): Int {
        val wanted = periodKey(plan, date)
        return plan.completions.entries.sumOf { (key, value) ->
            if (periodKey(plan, LocalDate.parse(key)) == wanted) value else 0
        }
    }

    fun progress(plan: Plan, date: LocalDate) = PlanProgress(countInPeriod(plan, date), plan.targetCount.coerceAtLeast(1))

    fun history(plan: Plan, until: LocalDate): PlanHistory {
        val start = LocalDate.parse(plan.startDate)
        if (until.isBefore(start)) return PlanHistory(0, 0, plan.completions.values.sum())
        val declaredEnd = plan.endDate.takeIf(String::isNotBlank)?.let(LocalDate::parse)
        val end = if (declaredEnd != null && declaredEnd.isBefore(until)) declaredEnd else until
        val periods = linkedSetOf<String>()
        var cursor = start
        var guard = 0
        while (!cursor.isAfter(end) && guard++ < 1500) {
            periods += periodKey(plan, cursor)
            cursor = cursor.plusDays(1)
        }
        val successful = periods.count { wanted ->
            plan.completions.entries.sumOf { (key, value) ->
                if (periodKey(plan, LocalDate.parse(key)) == wanted) value else 0
            } >= plan.targetCount
        }
        return PlanHistory(periods.size, successful, plan.completions.values.sum())
    }

    fun executionsForDate(plans: List<Plan>, date: LocalDate): Int =
        plans.filter { isActive(it, date) }.sumOf { it.completions[date.toString()] ?: 0 }
}

data class SseEvent(val event: String, val data: String)

data class HermesStreamProjection(val conversationId: String, val content: String = "") {
    fun append(delta: String) = copy(content = content + delta)
    fun textFor(activeConversationId: String?) = content.takeIf { activeConversationId == conversationId }.orEmpty()
}

sealed interface HermesStreamEvent {
    data class Started(val conversation: HermesConversation, val userMessage: HermesMessage) : HermesStreamEvent
    data class Delta(val content: String) : HermesStreamEvent
    data class Completed(val conversation: HermesConversation, val message: HermesMessage) : HermesStreamEvent
    data class Failed(val detail: String) : HermesStreamEvent
}

fun OrbitJson.hermesStream(event: SseEvent): HermesStreamEvent {
    val obj = JSONObject(event.data)
    return when (event.event) {
        "started" -> HermesStreamEvent.Started(
            conversation(obj.optJSONObject("conversation") ?: JSONObject()),
            message(obj.optJSONObject("userMessage") ?: JSONObject()),
        )
        "delta" -> HermesStreamEvent.Delta(obj.optString("content"))
        "completed" -> HermesStreamEvent.Completed(
            conversation(obj.optJSONObject("conversation") ?: JSONObject()),
            message(obj.optJSONObject("message") ?: JSONObject()),
        )
        "error" -> HermesStreamEvent.Failed(obj.optString("detail", "Hermes 运行失败"))
        else -> HermesStreamEvent.Failed("Hermes 返回了未知事件：${event.event}")
    }
}

class SseParser {
    private var buffer = ""

    fun feed(chunk: String): List<SseEvent> {
        buffer += chunk
        val events = mutableListOf<SseEvent>()
        while (true) {
            val match = Regex("\\r?\\n\\r?\\n").find(buffer) ?: break
            val block = buffer.substring(0, match.range.first)
            buffer = buffer.substring(match.range.last + 1)
            var event = "message"
            val data = mutableListOf<String>()
            block.lineSequence().forEach { line ->
                when {
                    line.startsWith("event:") -> event = line.substringAfter(':').trim()
                    line.startsWith("data:") -> data += line.substringAfter(':').trimStart()
                }
            }
            if (data.isNotEmpty()) events += SseEvent(event, data.joinToString("\n"))
        }
        return events
    }
}

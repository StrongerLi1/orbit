package cloud.shawnstronger.orbit

import android.content.Context
import androidx.core.content.edit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpCookie
import java.net.HttpURLConnection
import java.net.URLEncoder
import java.net.URL
import java.nio.charset.StandardCharsets

class OrbitHttpException(val status: Int, message: String) : Exception(message)

class OrbitClient(context: Context) {
    private val preferences = context.getSharedPreferences("orbit_android", Context.MODE_PRIVATE)
    private val refreshLock = Any()
    private val cookieLock = Any()
    @Volatile private var cookieRevision = 0
    @Volatile private var activeStream: HttpURLConnection? = null

    var origin: String = preferences.getString(SERVER_OVERRIDE, null)?.takeIf(String::isNotBlank) ?: BuildConfig.DEFAULT_SERVER
        private set

    init {
        if (shouldDiscardCookies(preferences.getString(COOKIE_ORIGIN, null), origin)) clearCookies()
    }

    suspend fun restoreUser(): OrbitUser = OrbitJson.user(request("GET", "/api/auth/me"))

    suspend fun captchaToken(): String = JSONObject(request("POST", "/api/auth/playcaptcha", JSONObject(), retry = false)).optString("token")

    suspend fun authenticate(username: String, password: String, captchaToken: String, register: Boolean): OrbitUser {
        val payload = JSONObject()
            .put("username", username.trim())
            .put("password", password)
            .put("playcaptchaToken", captchaToken)
        val path = if (register) "/api/auth/register" else "/api/auth/login"
        return OrbitJson.user(request("POST", path, payload, retry = false))
    }

    suspend fun logout() {
        runCatching { request("POST", "/api/auth/logout", JSONObject(), retry = false) }
        clearCookies()
    }

    suspend fun bookmarks() = OrbitJson.bookmarks(request("GET", "/api/bookmarks"))
    suspend fun todos() = OrbitJson.todos(request("GET", "/api/todos"))
    suspend fun plans() = OrbitJson.plans(request("GET", "/api/plans"))
    suspend fun folders() = OrbitJson.folders(request("GET", "/api/folders"))
    suspend fun excerpts() = OrbitJson.excerpts(request("GET", "/api/excerpts"))

    suspend fun create(collection: String, payload: JSONObject) = request("POST", "/api/$collection", payload)
    suspend fun patch(collection: String, id: String, payload: JSONObject) = request("PATCH", "/api/$collection/$id", payload)
    suspend fun delete(collection: String, id: String) = request("DELETE", "/api/$collection/$id")

    suspend fun searchNetdisk(keyword: String): NetdiskSearch {
        val query = URLEncoder.encode(keyword.trim(), StandardCharsets.UTF_8.name())
        return OrbitJson.netdisk(request("GET", "/api/netdisk/search?kw=$query"))
    }

    suspend fun conversations(admin: Boolean = false): List<HermesConversation> {
        val path = if (admin) "/api/admin/hermes-chat/conversations" else "/api/hermes-chat/conversations"
        return OrbitJson.conversations(request("GET", path))
    }

    suspend fun conversation(id: String, admin: Boolean = false): HermesConversation {
        val prefix = if (admin) "/api/admin/hermes-chat/conversations" else "/api/hermes-chat/conversations"
        return OrbitJson.conversation(request("GET", "$prefix/$id"))
    }

    suspend fun createConversation(): HermesConversation =
        OrbitJson.conversation(request("POST", "/api/hermes-chat/conversations", JSONObject()))

    suspend fun deleteConversation(id: String, admin: Boolean = false) {
        val prefix = if (admin) "/api/admin/hermes-chat/conversations" else "/api/hermes-chat/conversations"
        request("DELETE", "$prefix/$id")
    }

    suspend fun stopHermes(id: String) {
        request("POST", "/api/hermes-chat/conversations/$id/messages/stop", JSONObject())
        activeStream?.disconnect()
    }

    suspend fun streamHermes(id: String, content: String, onEvent: suspend (SseEvent) -> Unit) = withContext(Dispatchers.IO) {
        val payload = JSONObject().put("content", content).toString()
        val path = "/api/hermes-chat/conversations/$id/messages/stream"
        val revision = cookieRevision
        var connection = open(path, "POST", payload, accept = "text/event-stream")
        if (connection.responseCode == 401) {
            connection.disconnect()
            refreshIfNeeded(revision)
            connection = open(path, "POST", payload, accept = "text/event-stream")
        }
        activeStream = connection
        try {
            captureCookies(connection)
            val status = connection.responseCode
            if (status !in 200..299) throw httpError(connection, status)
            val contentType = connection.contentType.orEmpty()
            if (!contentType.contains("text/event-stream")) throw OrbitHttpException(502, "Hermes 流式响应格式无效")
            val parser = SseParser()
            connection.inputStream.bufferedReader().use { reader ->
                val chars = CharArray(2048)
                while (true) {
                    val count = reader.read(chars)
                    if (count < 0) break
                    parser.feed(String(chars, 0, count)).forEach { onEvent(it) }
                }
            }
        } finally {
            if (activeStream === connection) activeStream = null
            connection.disconnect()
        }
    }

    fun disconnectStream() {
        activeStream?.disconnect()
        activeStream = null
    }

    suspend fun adminUsers() = OrbitJson.adminUsers(request("GET", "/api/admin/users"))
    suspend fun adminRoles() = OrbitJson.roles(request("GET", "/api/admin/roles"))
    suspend fun adminPermissions() = OrbitJson.permissions(request("GET", "/api/admin/permissions"))
    suspend fun updateRoles(id: String, roles: List<String>) = OrbitJson.adminUsers(
        JSONArray().put(JSONObject(request("PATCH", "/api/admin/users/$id/roles", JSONObject().put("roles", JSONArray(roles))))).toString()
    ).first()
    suspend fun setBanned(id: String, banned: Boolean) = request("PATCH", "/api/admin/users/$id/ban", JSONObject().put("banned", banned))
    suspend fun deleteUser(id: String) = request("DELETE", "/api/admin/users/$id")

    suspend fun hermesStatus(): HermesStatus = OrbitJson.hermesStatus(request("GET", "/api/agents/hermes/status"))
    suspend fun hermesAction(action: String): HermesStatus =
        OrbitJson.hermesStatus(request("POST", "/api/agents/hermes/$action", JSONObject()))

    fun setServerOverride(value: String?) {
        val next = ServerOriginPolicy.resolve(value, BuildConfig.DEFAULT_SERVER)
        preferences.edit {
            if (next == BuildConfig.DEFAULT_SERVER) remove(SERVER_OVERRIDE) else putString(SERVER_OVERRIDE, next)
        }
        origin = next
        clearCookies()
    }

    fun cookiePairs(): List<String> = synchronized(cookieLock) {
        val values = JSONObject(preferences.getString(COOKIES, "{}") ?: "{}")
        values.keys().asSequence().map { name -> "$name=${values.optString(name)}" }.toList()
    }

    private suspend fun request(
        method: String,
        path: String,
        body: JSONObject? = null,
        retry: Boolean = true,
    ): String = withContext(Dispatchers.IO) {
        val revision = cookieRevision
        try {
            execute(method, path, body?.toString())
        } catch (error: OrbitHttpException) {
            if (error.status != 401 || !retry || path in NON_REFRESHABLE_AUTH_PATHS) throw error
            refreshIfNeeded(revision)
            execute(method, path, body?.toString())
        }
    }

    private fun refreshIfNeeded(failedAtRevision: Int) = synchronized(refreshLock) {
        if (cookieRevision != failedAtRevision) return@synchronized
        try {
            execute("POST", "/api/auth/refresh", "{}")
        } catch (failure: Exception) {
            clearCookies()
            throw failure
        }
    }

    private fun execute(method: String, path: String, body: String?): String {
        val connection = open(path, method, body)
        try {
            val status = connection.responseCode
            captureCookies(connection)
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            if (status !in 200..299) throw errorFrom(status, text)
            return text
        } finally {
            connection.disconnect()
        }
    }

    private fun open(path: String, method: String, body: String?, accept: String = "application/json"): HttpURLConnection {
        val connection = URL(origin + path).openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.connectTimeout = 15_000
        connection.readTimeout = if (accept == "text/event-stream") 0 else 45_000
        connection.setRequestProperty("Accept", accept)
        connection.setRequestProperty("Content-Type", "application/json")
        cookieHeader().takeIf(String::isNotBlank)?.let { connection.setRequestProperty("Cookie", it) }
        if (body != null) {
            connection.doOutput = true
            connection.outputStream.bufferedWriter().use { it.write(body) }
        }
        return connection
    }

    private fun captureCookies(connection: HttpURLConnection) {
        val headers = connection.headerFields.entries
            .filter { (name, _) -> name?.equals("Set-Cookie", ignoreCase = true) == true }
            .flatMap { it.value.orEmpty() }
        if (headers.isEmpty()) return
        synchronized(cookieLock) {
            val values = JSONObject(preferences.getString(COOKIES, "{}") ?: "{}")
            headers.forEach { header ->
                HttpCookie.parse(header).forEach { cookie ->
                    if (cookie.maxAge == 0L || cookie.value.isNullOrBlank()) values.remove(cookie.name)
                    else values.put(cookie.name, cookie.value)
                }
            }
            preferences.edit {
                putString(COOKIES, values.toString())
                putString(COOKIE_ORIGIN, origin)
            }
            cookieRevision++
        }
    }

    private fun cookieHeader(): String = cookiePairs().joinToString("; ")

    private fun clearCookies() = synchronized(cookieLock) {
        preferences.edit {
            remove(COOKIES)
            putString(COOKIE_ORIGIN, origin)
        }
        cookieRevision++
    }

    private fun httpError(connection: HttpURLConnection, status: Int): OrbitHttpException {
        val text = connection.errorStream?.bufferedReader()?.use { it.readText() }.orEmpty()
        return errorFrom(status, text)
    }

    private fun errorFrom(status: Int, text: String): OrbitHttpException {
        val message = runCatching { JSONObject(text).optString("error") }.getOrNull().orEmpty()
        return OrbitHttpException(status, message.ifBlank { "请求失败：HTTP $status" })
    }

    private companion object {
        const val SERVER_OVERRIDE = "server_override"
        const val COOKIES = "cookies"
        const val COOKIE_ORIGIN = "cookie_origin"
        val NON_REFRESHABLE_AUTH_PATHS = setOf(
            "/api/auth/playcaptcha",
            "/api/auth/register",
            "/api/auth/login",
            "/api/auth/refresh",
            "/api/auth/logout",
        )
    }
}

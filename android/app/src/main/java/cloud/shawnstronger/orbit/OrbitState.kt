package cloud.shawnstronger.orbit

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

class OrbitState(val client: OrbitClient) {
    private val stateScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var hermesJob: Job? = null
    private val latestLibraryRequest = LatestLibraryRequest()

    var bootstrapping by mutableStateOf(true)
    var busy by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var contentError by mutableStateOf<String?>(null)
    var user by mutableStateOf<OrbitUser?>(null)

    var bookmarks by mutableStateOf(emptyList<Bookmark>())
    var bookmarkSearch by mutableStateOf("")
    var folders by mutableStateOf(emptyList<Folder>())
    var todos by mutableStateOf(emptyList<Todo>())
    var todoLabels by mutableStateOf(emptyList<TodoLabel>())
    var plans by mutableStateOf(emptyList<Plan>())
    var excerpts by mutableStateOf(emptyList<Excerpt>())
    var writings by mutableStateOf(emptyList<WritingPost>())
    var filmRolls by mutableStateOf(emptyList<FilmRoll>())

    var libraryBooks by mutableStateOf(emptyList<LibraryBook>())
    var libraryQuery by mutableStateOf("")
    var libraryLoading by mutableStateOf(false)
    var libraryError by mutableStateOf<String?>(null)
    var activeLibraryBookId by mutableStateOf<String?>(null)
    var libraryReaders by mutableStateOf<LibraryReaders?>(null)
    var libraryReviews by mutableStateOf<List<LibraryReview>?>(null)
    var librarySharePath by mutableStateOf("")
    var kindleSettings by mutableStateOf<KindleSettings?>(null)
    var kindleSendingBookId by mutableStateOf<String?>(null)
    var kindleError by mutableStateOf<String?>(null)
    var kindleNotice by mutableStateOf("")

    var netdisk by mutableStateOf<NetdiskSearch?>(null)
    var conversations by mutableStateOf(emptyList<HermesConversation>())
    var activeConversation by mutableStateOf<HermesConversation?>(null)
    var streaming by mutableStateOf(false)
    var stopping by mutableStateOf(false)
    var streamProjection by mutableStateOf<HermesStreamProjection?>(null)

    var adminUsers by mutableStateOf(emptyList<AdminUser>())
    var roles by mutableStateOf(emptyList<OrbitRole>())
    var permissions by mutableStateOf(emptyList<PermissionInfo>())
    var auditedConversations by mutableStateOf(emptyList<HermesConversation>())
    var auditedConversation by mutableStateOf<HermesConversation?>(null)
    var hermesStatus by mutableStateOf<HermesStatus?>(null)

    suspend fun bootstrap() {
        bootstrapping = true
        try {
            user = client.restoreUser()
        } catch (failure: OrbitHttpException) {
            if (failure.status != 401) error = failure.message
            user = null
        } catch (failure: Exception) {
            error = readable(failure)
            user = null
        }
        if (user != null) {
            try {
                loadContentOrThrow()
            } catch (failure: OrbitHttpException) {
                if (failure.status == 401) resetSession() else error = readable(failure)
            } catch (failure: Exception) {
                error = readable(failure)
            }
        }
        bootstrapping = false
    }

    suspend fun authenticate(username: String, password: String, register: Boolean): Boolean = guarded {
        require(username.trim().length in 3..32) { "用户名长度需要 3-32 位" }
        require(password.length >= 8) { "密码至少需要 8 位" }
        val token = client.captchaToken()
        user = client.authenticate(username, password, token, register)
        loadContentOrThrow()
    }

    suspend fun logout() {
        busy = true
        client.logout()
        resetSession()
        busy = false
    }

    suspend fun refreshContent(): Boolean = guarded { loadContentOrThrow() }

    suspend fun addBookmark(title: String, url: String, category: String, note: String) = mutate {
        client.create("bookmarks", JSONObject().put("title", title).put("url", url).put("category", category).put("note", note))
    }

    suspend fun toggleFavorite(item: Bookmark) = mutate {
        client.patch("bookmarks", item.id, JSONObject().put("favorite", !item.favorite))
    }

    suspend fun moveBookmark(item: Bookmark, category: String) = mutate {
        client.patch("bookmarks", item.id, JSONObject().put("category", category))
    }

    suspend fun addFolder(name: String) = mutate { client.create("folders", JSONObject().put("name", name)) }

    suspend fun moveFolder(index: Int, delta: Int): Boolean = guarded {
        val ordered = folders.sortedBy { it.sortOrder }.toMutableList()
        val target = index + delta
        if (index !in ordered.indices || target !in ordered.indices) return@guarded
        val moved = ordered.removeAt(index)
        ordered.add(target, moved)
        ordered.forEachIndexed { position, folder ->
            client.patch("folders", folder.id, JSONObject().put("sortOrder", position))
        }
        loadContentOrThrow()
    }

    suspend fun addExcerpt(content: String, author: String, source: String, date: String, note: String) = mutate {
        client.create(
            "excerpts",
            JSONObject().put("content", content).put("author", author).put("source", source).put("excerptDate", date).put("note", note),
        )
    }

    suspend fun updateExcerpt(id: String, content: String, author: String, source: String, date: String, note: String) = mutate {
        client.patch(
            "excerpts",
            id,
            JSONObject().put("content", content).put("author", author).put("source", source).put("excerptDate", date).put("note", note),
        )
    }

    suspend fun addWriting(content: String, visibility: String, anonymous: Boolean) = mutate {
        client.create("writings", writingPayload(content, visibility, anonymous))
    }

    suspend fun updateWriting(id: String, content: String, visibility: String, anonymous: Boolean) = mutate {
        client.patch("writings", id, writingPayload(content, visibility, anonymous))
    }

    suspend fun addFilmRoll(filmStock: String, iso: Int?, camera: String, status: String) = mutate {
        client.create("film-rolls", filmRollPayload(filmStock, iso, camera, status))
    }

    suspend fun updateFilmRoll(id: String, filmStock: String, iso: Int?, camera: String, status: String) = mutate {
        client.patch("film-rolls", id, filmRollPayload(filmStock, iso, camera, status))
    }

    suspend fun updateFilmRollStatus(item: FilmRoll, status: String) =
        updateFilmRoll(item.id, item.filmStock, item.iso, item.camera, status)

    suspend fun addFilmExposure(
        rollId: String,
        frameNumber: Int,
        takenAt: String,
        location: String,
        thoughts: String,
        lens: String,
        aperture: String,
        shutterSpeed: String,
    ) = mutate {
        client.createFilmExposure(
            rollId,
            filmExposurePayload(frameNumber, takenAt, location, thoughts, lens, aperture, shutterSpeed),
        )
    }

    suspend fun updateFilmExposure(
        item: FilmExposure,
        frameNumber: Int,
        takenAt: String,
        location: String,
        thoughts: String,
        lens: String,
        aperture: String,
        shutterSpeed: String,
    ) = mutate {
        client.updateFilmExposure(
            item.rollId,
            item.id,
            filmExposurePayload(frameNumber, takenAt, location, thoughts, lens, aperture, shutterSpeed),
        )
    }

    suspend fun deleteFilmExposure(item: FilmExposure) = mutate {
        client.deleteFilmExposure(item.rollId, item.id)
    }

    suspend fun loadLibrary(query: String = libraryQuery): Boolean {
        val generation = latestLibraryRequest.next()
        libraryQuery = query
        libraryLoading = true
        libraryError = null
        return try {
            val result = client.libraryBooks(query)
            if (latestLibraryRequest.accepts(generation)) libraryBooks = result
            true
        } catch (failure: Exception) {
            if (failure is OrbitHttpException && failure.status == 401) resetSession()
            else if (latestLibraryRequest.accepts(generation)) libraryError = readable(failure)
            false
        } finally {
            if (latestLibraryRequest.accepts(generation)) libraryLoading = false
        }
    }

    suspend fun libraryCover(bookId: String): ByteArray? = try {
        client.libraryCover(bookId)
    } catch (failure: OrbitHttpException) {
        if (failure.status == 401) resetSession()
        null
    } catch (_: Exception) {
        null
    }

    suspend fun uploadLibraryBook(title: String, author: String, book: LibraryUploadFile, cover: LibraryUploadFile?) =
        libraryMutation(mutate = { client.uploadLibraryBook(title, author, book, cover) })

    suspend fun updateLibraryBook(
        bookId: String,
        title: String,
        author: String,
        removeCover: Boolean,
        cover: LibraryUploadFile?,
    ) = libraryMutation(mutate = { client.updateLibraryBook(bookId, title, author, removeCover, cover) })

    suspend fun deleteLibraryBook(bookId: String) = libraryMutation(mutate = {
        client.deleteLibraryBook(bookId)
        if (activeLibraryBookId == bookId) clearLibraryDetail()
    })

    suspend fun loadLibraryReaders(bookId: String): Boolean = guarded {
        activeLibraryBookId = bookId
        libraryReaders = null
        libraryReaders = client.libraryReaders(bookId)
    }

    suspend fun createLibraryRead(bookId: String, readDate: String, review: String, anonymous: Boolean): Boolean = libraryMutation(
        mutate = { client.createLibraryRead(bookId, readDate, review, anonymous) },
        refresh = {
            refreshLibraryOrThrow()
            libraryReaders = client.libraryReaders(bookId)
            if (review.isNotBlank()) libraryReviews = client.libraryReviews(bookId)
        },
    )

    suspend fun updateLibraryRead(bookId: String, readId: String, readDate: String): Boolean = libraryMutation(
        mutate = { client.updateLibraryRead(bookId, readId, readDate) },
        refresh = { refreshLibraryOrThrow(); libraryReaders = client.libraryReaders(bookId) },
    )

    suspend fun deleteLibraryRead(bookId: String, readId: String): Boolean = libraryMutation(
        mutate = { client.deleteLibraryRead(bookId, readId) },
        refresh = { refreshLibraryOrThrow(); libraryReaders = client.libraryReaders(bookId) },
    )

    suspend fun loadLibraryReviews(bookId: String): Boolean = guarded {
        activeLibraryBookId = bookId
        libraryReviews = null
        libraryReviews = client.libraryReviews(bookId)
    }

    suspend fun createLibraryReview(bookId: String, content: String, anonymous: Boolean): Boolean = libraryMutation(
        mutate = {
            require(content.isNotBlank() && content.length <= 3000) { "书评需要 1-3000 个字符" }
            client.createLibraryReview(bookId, content, anonymous)
        },
        refresh = { libraryReviews = client.libraryReviews(bookId) },
    )

    suspend fun toggleLibraryReview(bookId: String, review: LibraryReview): Boolean = libraryMutation(
        mutate = {
            require(review.canToggleAnonymous) { "不能修改这条书评" }
            client.toggleLibraryReview(bookId, review.id, !review.isAnonymous)
        },
        refresh = { libraryReviews = client.libraryReviews(bookId) },
    )

    suspend fun deleteLibraryReview(bookId: String, review: LibraryReview): Boolean = libraryMutation(
        mutate = {
            require(review.canDelete) { "不能删除这条书评" }
            client.deleteLibraryReview(bookId, review.id)
        },
        refresh = { libraryReviews = client.libraryReviews(bookId) },
    )

    suspend fun loadLibraryShare(bookId: String, regenerate: Boolean = false): Boolean = guarded {
        activeLibraryBookId = bookId
        if (!regenerate) librarySharePath = ""
        librarySharePath = client.libraryShare(bookId, regenerate)
    }

    suspend fun revokeLibraryShare(bookId: String): Boolean = guarded {
        client.revokeLibraryShare(bookId)
        librarySharePath = ""
    }

    suspend fun downloadLibraryBook(bookId: String, openOutput: () -> java.io.OutputStream): Boolean = guarded {
        client.downloadLibraryBook(bookId, openOutput)
    }

    suspend fun loadKindleSettings(): KindleSettings? = try {
        kindleError = null
        client.kindleSettings().also { kindleSettings = it }
    } catch (failure: Exception) {
        if (failure is OrbitHttpException && failure.status == 401) resetSession() else kindleError = readable(failure)
        null
    }

    suspend fun saveKindleEmail(email: String): Boolean = kindleAction {
        require(Regex("^[^@\\s]+@kindle\\.com$", RegexOption.IGNORE_CASE).matches(email.trim())) { "请输入有效的 @kindle.com 邮箱" }
        kindleSettings = client.saveKindleEmail(email)
        kindleNotice = "Kindle 邮箱已保存"
    }

    suspend fun clearKindleEmail(): Boolean = kindleAction {
        kindleSettings = client.clearKindleEmail()
        kindleNotice = "Kindle 邮箱已清除"
    }

    suspend fun sendLibraryBookToKindle(bookId: String): Boolean {
        if (kindleSendingBookId != null) return false
        kindleSendingBookId = bookId
        kindleError = null
        return try {
            client.sendLibraryBookToKindle(bookId)
            kindleNotice = "邮件已发送，请稍后在 Kindle 中查看"
            true
        } catch (failure: Exception) {
            if (failure is OrbitHttpException && failure.status == 401) resetSession() else kindleError = readable(failure)
            false
        } finally {
            kindleSendingBookId = null
        }
    }

    fun clearLibraryDetail() {
        activeLibraryBookId = null
        libraryReaders = null
        libraryReviews = null
        librarySharePath = ""
    }

    private suspend fun kindleAction(action: suspend () -> Unit): Boolean {
        kindleError = null
        return try {
            action()
            true
        } catch (failure: Exception) {
            if (failure is OrbitHttpException && failure.status == 401) resetSession() else kindleError = readable(failure)
            false
        }
    }

    suspend fun addTodo(title: String, priority: String, dueDate: String, labelId: String?) = mutate {
        client.create("todos", JSONObject().put("title", title).put("priority", priority).put("dueDate", dueDate).put("labelId", labelId ?: JSONObject.NULL))
    }

    suspend fun addTodoLabel(name: String) = mutate { client.create("todo-labels", JSONObject().put("name", name)) }
    suspend fun renameTodoLabel(label: TodoLabel, name: String) = mutate { client.patch("todo-labels", label.id, JSONObject().put("name", name)) }
    suspend fun deleteTodoLabel(label: TodoLabel) = mutate { client.delete("todo-labels", label.id) }
    suspend fun moveTodo(item: Todo, labelId: String?) = mutate { client.patch("todos", item.id, JSONObject().put("labelId", labelId ?: JSONObject.NULL)) }

    suspend fun toggleTodo(item: Todo) = mutate {
        client.patch("todos", item.id, JSONObject().put("completed", !item.completed))
    }

    suspend fun clearCompleted() = mutate {
        todos.filter { it.completed }.forEach { client.delete("todos", it.id) }
    }

    suspend fun addPlan(
        title: String,
        frequency: String,
        target: Int,
        start: String,
        end: String,
        time: String,
        duration: Int,
        color: String,
    ) = mutate {
        client.create(
            "plans",
            JSONObject().put("title", title).put("frequencyType", frequency).put("targetCount", target)
                .put("startDate", start).put("endDate", end).put("time", time).put("duration", duration).put("color", color),
        )
    }

    suspend fun changePlanCount(plan: Plan, date: String, delta: Int) = mutate {
        val completions = plan.completions.toMutableMap()
        val next = ((completions[date] ?: 0) + delta).coerceAtLeast(0)
        if (next == 0) completions.remove(date) else completions[date] = next
        val payload = JSONObject()
        completions.forEach { (key, value) -> payload.put(key, value) }
        client.patch("plans", plan.id, JSONObject().put("completions", payload))
    }

    suspend fun deleteContent(collection: String, id: String) = mutate { client.delete(collection, id) }

    suspend fun searchNetdisk(keyword: String): Boolean = guarded { netdisk = client.searchNetdisk(keyword) }

    suspend fun loadConversations(): Boolean = guarded {
        conversations = client.conversations()
        val wanted = activeConversation?.id?.takeIf { id -> conversations.any { it.id == id } } ?: conversations.firstOrNull()?.id
        activeConversation = wanted?.let { client.conversation(it) }
    }

    suspend fun openConversation(id: String): Boolean = guarded { activeConversation = client.conversation(id) }

    suspend fun newConversation(): Boolean = guarded {
        require(!streaming) { "请先停止或等待当前回答" }
        val created = client.createConversation()
        conversations = listOf(created) + conversations.filterNot { it.id == created.id }
        activeConversation = created
    }

    suspend fun deleteConversation(id: String): Boolean = guarded {
        require(!streaming) { "请先停止或等待当前回答" }
        client.deleteConversation(id)
        conversations = client.conversations()
        activeConversation = conversations.firstOrNull()?.let { client.conversation(it.id) }
    }

    fun beginHermes(content: String): Boolean {
        val current = activeConversation ?: return false
        if (streaming || content.isBlank()) return false
        error = null
        streaming = true
        streamProjection = HermesStreamProjection(current.id)
        stopping = false
        hermesJob = stateScope.launch { runHermes(current, content.trim()) }
        return true
    }

    fun beginHermesRecovery() {
        val current = activeConversation?.takeIf { it.generating } ?: return
        if (streaming) return
        error = null
        streaming = true
        streamProjection = HermesStreamProjection(current.id)
        stopping = false
        hermesJob = stateScope.launch {
            try {
                recoverHermes(current.id)
            } catch (failure: Exception) {
                handleHermesFailure(failure)
            } finally {
                finishHermesState()
            }
        }
    }

    private suspend fun runHermes(current: HermesConversation, content: String) {
        var completed = false
        try {
            client.streamHermes(current.id, content) { raw ->
                withContext(Dispatchers.Main) {
                    when (val event = OrbitJson.hermesStream(raw)) {
                        is HermesStreamEvent.Started -> {
                            conversations = listOf(event.conversation) + conversations.filterNot { it.id == event.conversation.id }
                            if (activeConversation?.id == current.id) {
                                activeConversation = event.conversation.copy(
                                    messages = activeConversation.orEmptyMessages() + event.userMessage,
                                )
                            }
                        }
                        is HermesStreamEvent.Delta -> streamProjection = streamProjection?.append(event.content)
                        is HermesStreamEvent.Completed -> completed = true
                        is HermesStreamEvent.Failed -> throw OrbitHttpException(502, event.detail)
                    }
                }
            }
            if (completed) {
                val persisted = client.conversation(current.id)
                if (activeConversation?.id == current.id) activeConversation = persisted
                conversations = client.conversations()
            } else if (!stopping) {
                recoverHermes(current.id)
            }
        } catch (failure: Exception) {
            if (!stopping) {
                runCatching { recoverHermes(current.id) }.onFailure { recoveryFailure -> handleHermesFailure(recoveryFailure) }
            }
        } finally {
            finishHermesState()
        }
    }

    suspend fun stopHermes(): Boolean {
        val id = streamProjection?.conversationId ?: activeConversation?.takeIf { it.generating }?.id ?: return false
        stopping = true
        return try {
            client.stopHermes(id)
            delay(350)
            val persisted = client.conversation(id)
            if (activeConversation?.id == id) activeConversation = persisted
            conversations = client.conversations()
            true
        } catch (failure: Exception) {
            error = readable(failure)
            false
        } finally {
            stopping = false
        }
    }

    suspend fun loadAdmin(): Boolean = guarded {
        adminUsers = client.adminUsers()
        roles = client.adminRoles()
        permissions = client.adminPermissions()
        auditedConversations = client.conversations(admin = true)
    }

    suspend fun setUserRole(item: AdminUser, role: String, enabled: Boolean): Boolean = guarded {
        val next = item.roles.toMutableSet().apply { if (enabled) add(role) else remove(role) }.toList()
        client.updateRoles(item.id, next)
        adminUsers = client.adminUsers()
        if (item.id == user?.id) user = client.restoreUser()
    }

    suspend fun setUserBanned(item: AdminUser, banned: Boolean): Boolean = guarded {
        client.setBanned(item.id, banned)
        adminUsers = client.adminUsers()
    }

    suspend fun deleteUser(item: AdminUser): Boolean = guarded {
        client.deleteUser(item.id)
        adminUsers = client.adminUsers()
    }

    suspend fun openAudit(id: String): Boolean = guarded { auditedConversation = client.conversation(id, admin = true) }

    suspend fun deleteAudit(id: String): Boolean = guarded {
        client.deleteConversation(id, admin = true)
        auditedConversations = client.conversations(admin = true)
        if (auditedConversation?.id == id) auditedConversation = null
    }

    suspend fun loadHermesStatus(): Boolean = guarded { hermesStatus = client.hermesStatus() }
    suspend fun hermesAction(action: String): Boolean = guarded { hermesStatus = client.hermesAction(action) }

    fun changeServer(value: String?): Boolean = try {
        require(user?.isAdmin == true) { "只有管理员可以修改服务器地址" }
        client.setServerOverride(value)
        resetSession()
        true
    } catch (failure: Exception) {
        error = readable(failure)
        false
    }

    fun dismissError() { error = null }

    fun close() {
        hermesJob?.cancel()
        client.disconnectStream()
        stateScope.cancel()
    }

    private suspend fun recoverHermes(id: String) {
        while (true) {
            val recovered = try {
                client.conversation(id)
            } catch (failure: OrbitHttpException) {
                if (failure.status in listOf(401, 403, 404)) throw failure
                delay(3_000)
                continue
            } catch (_: Exception) {
                delay(3_000)
                continue
            }
            if (activeConversation?.id == id) activeConversation = recovered
            if (!recovered.generating) {
                conversations = client.conversations()
                return
            }
            delay(2_000)
        }
    }

    private suspend fun mutate(block: suspend () -> Unit): Boolean = libraryMutation(block) { loadContentOrThrow() }

    private suspend fun libraryMutation(
        mutate: suspend () -> Unit,
        refresh: suspend () -> Unit = { refreshLibraryOrThrow() },
    ): Boolean {
        busy = true
        error = null
        return try {
            mutate()
            try {
                refresh()
            } catch (failure: Exception) {
                if (failure is OrbitHttpException && failure.status == 401) resetSession()
                else error = "操作已完成，但刷新失败：${readable(failure)}"
            }
            true
        } catch (failure: Exception) {
            if (failure is OrbitHttpException && failure.status == 401) resetSession()
            error = readable(failure)
            false
        } finally {
            busy = false
        }
    }

    private suspend fun refreshLibraryOrThrow() {
        libraryBooks = client.libraryBooks(libraryQuery)
        libraryError = null
    }

    private suspend fun loadContentOrThrow() {
        val failures = loadContentSections(
            listOf(
                "收藏" to suspend { bookmarks = client.bookmarks() },
                "待办" to suspend { todos = client.todos() },
                "待办标签" to suspend { todoLabels = client.todoLabels() },
                "计划" to suspend { plans = client.plans() },
                "收藏夹" to suspend {
                    folders = client.folders().sortedWith(compareBy<Folder> { it.sortOrder }.thenByDescending { it.createdAt })
                },
                "摘录" to suspend { excerpts = client.excerpts() },
                "写点什么" to suspend { writings = client.writings() },
                "胶片日记" to suspend { filmRolls = client.filmRolls() },
            ),
        )

        contentError = failures.takeIf { it.isNotEmpty() }?.joinToString("\n") { "${it.label}：${it.detail}" }
        contentError?.let { throw IllegalStateException("部分服务器数据加载失败：\n$it") }
    }

    private suspend fun guarded(block: suspend () -> Unit): Boolean {
        busy = true
        error = null
        return try {
            block()
            true
        } catch (failure: Exception) {
            if (failure is OrbitHttpException && failure.status == 401) resetSession()
            error = readable(failure)
            false
        } finally {
            busy = false
        }
    }

    private fun resetSession() {
        hermesJob?.cancel()
        hermesJob = null
        client.disconnectStream()
        user = null
        bookmarks = emptyList()
        contentError = null
        bookmarkSearch = ""
        folders = emptyList()
        todos = emptyList()
        todoLabels = emptyList()
        plans = emptyList()
        excerpts = emptyList()
        writings = emptyList()
        filmRolls = emptyList()
        latestLibraryRequest.invalidate()
        libraryBooks = emptyList()
        libraryQuery = ""
        libraryLoading = false
        libraryError = null
        clearLibraryDetail()
        kindleSettings = null
        kindleSendingBookId = null
        kindleError = null
        kindleNotice = ""
        conversations = emptyList()
        activeConversation = null
        finishHermesState()
        adminUsers = emptyList()
    }

    private fun handleHermesFailure(failure: Throwable) {
        if (failure is OrbitHttpException && failure.status == 401) resetSession()
        else error = readable(failure)
    }

    private fun finishHermesState() {
        streaming = false
        streamProjection = null
        stopping = false
        hermesJob = null
    }

    private fun readable(failure: Throwable): String = when (failure) {
        is OrbitHttpException -> failure.message ?: "请求失败"
        is IllegalArgumentException -> failure.message ?: "输入无效"
        else -> failure.message ?: "暂时连接不上服务器"
    }

    private fun HermesConversation?.orEmptyMessages() = this?.messages ?: emptyList()

    private fun writingPayload(content: String, visibility: String, anonymous: Boolean) = JSONObject()
        .put("content", content)
        .put("visibility", visibility)
        .put("anonymous", anonymous)

    private fun filmRollPayload(filmStock: String, iso: Int?, camera: String, status: String) = JSONObject()
        .put("filmStock", filmStock)
        .put("iso", iso ?: JSONObject.NULL)
        .put("camera", camera)
        .put("status", status)

    private fun filmExposurePayload(
        frameNumber: Int,
        takenAt: String,
        location: String,
        thoughts: String,
        lens: String,
        aperture: String,
        shutterSpeed: String,
    ) = JSONObject()
        .put("frameNumber", frameNumber)
        .put("takenAt", takenAt)
        .put("location", location)
        .put("thoughts", thoughts)
        .put("lens", lens)
        .put("aperture", aperture)
        .put("shutterSpeed", shutterSpeed)
}

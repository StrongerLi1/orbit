package cloud.shawnstronger.orbit

import android.annotation.SuppressLint
import android.app.DatePickerDialog
import android.app.TimePickerDialog
import android.content.Intent
import android.net.Uri
import android.webkit.CookieManager
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.net.toUri
import kotlinx.coroutines.launch
import java.net.URI
import java.time.LocalDate
import java.time.LocalTime
import kotlin.math.roundToInt

@Composable
private fun Page(content: @Composable () -> Unit) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) { content() }
}

@Composable
private fun Metric(label: String, value: String, modifier: Modifier = Modifier) {
    Surface(modifier, shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceVariant) {
        Column(Modifier.padding(14.dp)) {
            Text(value, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun ExternalLink(label: String, url: String) {
    val context = LocalContext.current
    TextButton(onClick = { runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, url.toUri())) } }) {
        Text(label, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
fun DashboardScreen(state: OrbitState, onRoute: (OrbitRoute) -> Unit) {
    val today = LocalDate.now()
    val activePlans = state.plans.filter { runCatching { PlanMath.isActive(it, today) }.getOrDefault(false) }
    val completedPlans = activePlans.count { PlanMath.progress(it, today).let { progress -> progress.done >= progress.target } }
    val openTodos = state.todos.filterNot { it.completed }
    val excerpt = remember(state.excerpts) { state.excerpts.randomOrNull() }
    val scope = rememberCoroutineScope()
    Page {
        SectionTitle("今天", "${today} · ${state.client.origin}") {
            TextButton(onClick = { scope.launch { state.refreshContent() } }) { Text("刷新") }
        }
        state.contentError?.let { message ->
            Surface(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.error.copy(alpha = .1f), shape = MaterialTheme.shapes.medium) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("服务器数据未完整加载", fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.error)
                    Text(message)
                    Text("点击右上角“刷新”重试。", style = MaterialTheme.typography.labelMedium)
                }
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Metric("收藏", state.bookmarks.size.toString(), Modifier.weight(1f))
            Metric("今日计划", "$completedPlans/${activePlans.size}", Modifier.weight(1f))
            Metric("待办", openTodos.size.toString(), Modifier.weight(1f))
        }
        excerpt?.let {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("今日摘录", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                    Text(it.content, style = MaterialTheme.typography.titleMedium)
                    Text(listOf(it.author, it.source).filter(String::isNotBlank).joinToString(" · "), color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        Text("快速进入", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            items(listOf(OrbitRoute.Bookmarks, OrbitRoute.Netdisk, OrbitRoute.Excerpts, OrbitRoute.Plans, OrbitRoute.Todos)) { route ->
                AssistChip(onClick = { onRoute(route) }, label = { Text(route.label) })
            }
        }
        Text("今日计划", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        if (activePlans.isEmpty()) EmptyState("今天没有进行中的计划") else activePlans.forEach { plan ->
            val progress = PlanMath.progress(plan, today)
            Card(Modifier.fillMaxWidth()) {
                Row(Modifier.fillMaxWidth().padding(14.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    Column { Text(plan.title, fontWeight = FontWeight.SemiBold); Text("${plan.time} · ${plan.duration} 分钟") }
                    Text("${progress.done}/${progress.target}", color = MaterialTheme.colorScheme.primary)
                }
            }
        }
        Text("待办", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        if (openTodos.isEmpty()) EmptyState("待办已经清空") else openTodos.take(4).forEach { todo ->
            Text("• ${todo.title}${todo.dueDate.takeIf(String::isNotBlank)?.let { " · $it" }.orEmpty()}")
        }
        Text("最近收藏", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        if (state.bookmarks.isEmpty()) EmptyState("还没有收藏") else state.bookmarks.take(4).forEach { bookmark ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text(bookmark.title, Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
                ExternalLink("打开", bookmark.url)
            }
        }
    }
}

@Composable
fun BookmarksScreen(state: OrbitState) {
    var search by remember { mutableStateOf(state.bookmarkSearch) }
    var category by remember { mutableStateOf("全部") }
    var addBookmark by remember { mutableStateOf(false) }
    var addFolder by remember { mutableStateOf(false) }
    var move by remember { mutableStateOf<Bookmark?>(null) }
    var deleteFolder by remember { mutableStateOf<Folder?>(null) }
    val scope = rememberCoroutineScope()
    val canManage = state.user?.can("folders:manage") == true
    LaunchedEffect(state.bookmarkSearch) { search = state.bookmarkSearch }
    val visible = state.bookmarks.filter {
        (category == "全部" || it.category == category) &&
            (search.isBlank() || listOf(it.title, it.url, it.note, it.category).any { value -> value.contains(search, ignoreCase = true) })
    }.sortedWith(compareByDescending<Bookmark> { it.favorite }.thenBy { it.title })

    Page {
        SectionTitle("收藏夹", "共 ${state.bookmarks.size} 个网站") {
            Row { TextButton(onClick = { addFolder = true }) { Text("新建标签") }; Button(onClick = { addBookmark = true }) { Text("添加") } }
        }
        OutlinedTextField(search, { search = it; state.bookmarkSearch = it }, label = { Text("搜索名称、网址、备注或收藏夹") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            item { FilterChip(category == "全部", { category = "全部" }, { Text("全部") }) }
            itemsIndexed(state.folders) { index, folder ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    FilterChip(category == folder.name, { category = folder.name }, { Text(folder.name) })
                    if (canManage) {
                        TextButton(onClick = { scope.launch { state.moveFolder(index, -1) } }) { Text("↑") }
                        TextButton(onClick = { scope.launch { state.moveFolder(index, 1) } }) { Text("↓") }
                        TextButton(onClick = { deleteFolder = folder }) { Text("×") }
                    }
                }
            }
        }
        if (visible.isEmpty()) EmptyState("没有匹配的收藏") else visible.forEach { item ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(item.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                            Text(item.category, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                        }
                        TextButton(onClick = { scope.launch { state.toggleFavorite(item) } }) { Text(if (item.favorite) "★" else "☆") }
                    }
                    if (item.note.isNotBlank()) Text(item.note, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        ExternalLink("打开网站", item.url)
                        Row {
                            TextButton(onClick = { move = item }) { Text("移动") }
                            TextButton(onClick = { scope.launch { state.deleteContent("bookmarks", item.id) } }) { Text("删除") }
                        }
                    }
                }
            }
        }
    }
    if (addBookmark) BookmarkDialog(state.folders, { addBookmark = false }) { title, url, folder, note ->
        scope.launch { if (state.addBookmark(title, url, folder, note)) addBookmark = false }
    }
    if (addFolder) OneFieldDialog("新建收藏夹", "名称", { addFolder = false }) {
        scope.launch { if (state.addFolder(it)) addFolder = false }
    }
    move?.let { bookmark -> FolderDialog(state.folders, bookmark.category, { move = null }) { folder ->
        scope.launch { if (state.moveBookmark(bookmark, folder)) move = null }
    } }
    deleteFolder?.let { folder -> ConfirmDialog("删除收藏夹", "确定删除收藏夹「${folder.name}」吗？收藏夹内仍有网站时服务器会拒绝删除。", { deleteFolder = null }) {
        deleteFolder = null
        if (category == folder.name) category = "全部"
        scope.launch { state.deleteContent("folders", folder.id) }
    } }
}

@Composable
fun ExcerptsScreen(state: OrbitState) {
    var add by remember { mutableStateOf(false) }
    var editing by remember { mutableStateOf<Excerpt?>(null) }
    var shuffled by remember { mutableStateOf<Excerpt?>(null) }
    val scope = rememberCoroutineScope()
    Page {
        SectionTitle("摘录", "保存值得重读的句子") {
            Row { TextButton(onClick = { shuffled = state.excerpts.randomOrNull() }) { Text("随机一句") }; Button(onClick = { editing = null; add = true }) { Text("添加") } }
        }
        shuffled?.let { item ->
            Surface(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.primary.copy(alpha = .1f), shape = MaterialTheme.shapes.medium) {
                Text(item.content, Modifier.padding(18.dp), style = MaterialTheme.typography.titleMedium)
            }
        }
        if (state.excerpts.isEmpty()) EmptyState("还没有摘录") else state.excerpts.sortedByDescending { it.excerptDate.ifBlank { it.createdAt } }.forEach { item ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(item.content, style = MaterialTheme.typography.titleMedium)
                    Text(listOf(item.author, item.source, item.excerptDate).filter(String::isNotBlank).joinToString(" · "), color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("${item.createdByName} 摘录", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (item.note.isNotBlank()) Text(item.note)
                    if (item.canManage) {
                        Row(Modifier.align(Alignment.End)) {
                            TextButton(onClick = { add = false; editing = item }) { Text("编辑") }
                            TextButton(onClick = { scope.launch { state.deleteContent("excerpts", item.id) } }) { Text("删除") }
                        }
                    }
                }
            }
        }
    }
    if (add || editing != null) ExcerptDialog(editing, { add = false; editing = null }) { content, author, source, date, note ->
        scope.launch {
            val success = editing?.let { state.updateExcerpt(it.id, content, author, source, date, note) }
                ?: state.addExcerpt(content, author, source, date, note)
            if (success) { add = false; editing = null }
        }
    }
}

@Composable
fun PlansScreen(state: OrbitState) {
    var date by remember { mutableStateOf(LocalDate.now()) }
    var add by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val active = state.plans.filter { runCatching { PlanMath.isActive(it, date) }.getOrDefault(false) }
    val total = PlanMath.executionsForDate(state.plans, date)
    val minutes = active.sumOf { (it.completions[date.toString()] ?: 0) * it.duration }
    val periodDone = active.sumOf { minOf(PlanMath.progress(it, date).done, it.targetCount) }
    val periodTarget = active.sumOf { it.targetCount }
    val periodRate = if (periodTarget == 0) 0 else (periodDone * 100f / periodTarget).roundToInt()
    Page {
        SectionTitle("日常计划", "按日、周或月追踪目标") { Button(onClick = { add = true }) { Text("添加") } }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            OutlinedButton(onClick = { date = date.minusDays(1) }) { Text("前一天") }
            Text(date.toString(), fontWeight = FontWeight.SemiBold)
            OutlinedButton(onClick = { date = date.plusDays(1) }) { Text("后一天") }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
            TextButton(onClick = { date = LocalDate.now() }) { Text("回到今天") }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Metric("当日执行", total.toString(), Modifier.weight(1f))
            Metric("进行中", active.size.toString(), Modifier.weight(1f))
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Metric("投入分钟", minutes.toString(), Modifier.weight(1f))
            Metric("周期进度", "$periodRate%", Modifier.weight(1f))
        }
        if (active.isEmpty()) EmptyState("这一天没有进行中的计划") else active.forEach { plan ->
            val progress = PlanMath.progress(plan, date)
            val history = PlanMath.history(plan, date)
            val rate = if (history.periods == 0) 0 else (history.successful * 100f / history.periods).roundToInt()
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Column { Text(plan.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold); Text("${frequencyName(plan.frequencyType)} ${plan.targetCount} 次 · ${plan.time} · ${plan.duration} 分钟") }
                        Text("${progress.done}/${progress.target}", color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                    }
                    Text("历史达标率 $rate% · 累计执行 ${history.totalExecutions} 次", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        OutlinedButton(onClick = { scope.launch { state.changePlanCount(plan, date.toString(), -1) } }, enabled = (plan.completions[date.toString()] ?: 0) > 0) { Text("−") }
                        Spacer(Modifier.width(8.dp))
                        Button(onClick = { scope.launch { state.changePlanCount(plan, date.toString(), 1) } }) { Text("+ 完成") }
                        TextButton(onClick = { scope.launch { state.deleteContent("plans", plan.id) } }) { Text("删除") }
                    }
                }
            }
        }
        Text("最近 7 天", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        (6 downTo 0).forEach { offset ->
            val day = date.minusDays(offset.toLong())
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { Text(day.toString()); Text("${PlanMath.executionsForDate(state.plans, day)} 次") }
            HorizontalDivider()
        }
    }
    if (add) PlanDialog({ add = false }) { title, frequency, target, start, end, time, duration, color ->
        scope.launch { if (state.addPlan(title, frequency, target, start, end, time, duration, color)) add = false }
    }
}

private fun frequencyName(value: String) = when (value) { "weekly" -> "每周"; "monthly" -> "每月"; else -> "每日" }

@Composable
fun TodosScreen(state: OrbitState) {
    var add by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val sorted = state.todos.sortedWith(compareBy<Todo> { it.completed }.thenByDescending { priorityRank(it.priority) }.thenBy { it.dueDate })
    Page {
        SectionTitle("待办事项", "${state.todos.count { !it.completed }} 项未完成") { Button(onClick = { add = true }) { Text("添加") } }
        if (state.todos.any { it.completed }) TextButton(onClick = { scope.launch { state.clearCompleted() } }) { Text("清除所有已完成") }
        if (sorted.isEmpty()) EmptyState("没有待办，轻松一下") else sorted.forEachIndexed { index, item ->
            if (index == 0 || sorted[index - 1].completed != item.completed) {
                Text(if (item.completed) "已完成" else "进行中", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            }
            Card(Modifier.fillMaxWidth()) {
                Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(item.completed, { scope.launch { state.toggleTodo(item) } })
                    Column(Modifier.weight(1f)) {
                        Text(item.title, fontWeight = FontWeight.SemiBold, color = if (item.completed) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface)
                        Text("${priorityName(item.priority)}${item.dueDate.takeIf(String::isNotBlank)?.let { " · $it" }.orEmpty()}", style = MaterialTheme.typography.labelMedium)
                    }
                    TextButton(onClick = { scope.launch { state.deleteContent("todos", item.id) } }) { Text("删除") }
                }
            }
        }
    }
    if (add) TodoDialog({ add = false }) { title, priority, due -> scope.launch { if (state.addTodo(title, priority, due)) add = false } }
}

private fun priorityRank(value: String) = when (value) { "high" -> 3; "medium" -> 2; else -> 1 }
private fun priorityName(value: String) = when (value) { "high" -> "高优先级"; "low" -> "低优先级"; else -> "中优先级" }

@Composable
fun NetdiskScreen(state: OrbitState) {
    var query by remember { mutableStateOf("") }
    var source by remember { mutableStateOf("全部") }
    val scope = rememberCoroutineScope()
    val sources = listOf("全部") + (state.netdisk?.results?.map { it.source }?.filter(String::isNotBlank)?.distinct() ?: emptyList())
    val results = state.netdisk?.results?.filter { source == "全部" || it.source == source }.orEmpty()
    Page {
        SectionTitle("网盘搜索", "通过当前服务器聚合搜索结果")
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(query, { query = it }, label = { Text("搜索关键词") }, modifier = Modifier.weight(1f), singleLine = true)
            Button(onClick = { scope.launch { state.searchNetdisk(query) } }) { Text("搜索") }
        }
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) { items(sources) { value -> FilterChip(source == value, { source = value }, { Text(value) }) } }
        state.netdisk?.let { Text("来源服务：${it.source}", style = MaterialTheme.typography.labelSmall) }
        if (state.netdisk != null && results.isEmpty()) EmptyState("没有找到结果") else results.forEach { item ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(item.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(listOf(item.source, item.size, item.time).filter(String::isNotBlank).joinToString(" · "), color = MaterialTheme.colorScheme.primary)
                    if (item.description.isNotBlank()) Text(item.description, maxLines = 3, overflow = TextOverflow.Ellipsis)
                    ExternalLink("打开资源", item.url)
                }
            }
        }
    }
}

@Composable
fun HermesChatScreen(state: OrbitState) {
    var input by remember { mutableStateOf("") }
    var deleting by remember { mutableStateOf<HermesConversation?>(null) }
    val scope = rememberCoroutineScope()
    val active = state.activeConversation
    LaunchedEffect(active?.id, active?.generating) {
        if (active?.generating == true) state.beginHermesRecovery()
    }
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text("Hermes 聊天", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
            Button(onClick = { scope.launch { state.newConversation() } }, enabled = !state.streaming) { Text("新对话") }
        }
        LazyRow(Modifier.fillMaxWidth().padding(horizontal = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            items(state.conversations, key = { it.id }) { conversation ->
                AssistChip(onClick = { scope.launch { state.openConversation(conversation.id) } }, label = { Text(if (conversation.id == active?.id) "● ${conversation.title}" else conversation.title, maxLines = 1) })
            }
        }
        if (active == null) {
            Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) { EmptyState("新建一个对话开始使用 Hermes") }
        } else {
            LazyColumn(Modifier.weight(1f).fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(active.messages, key = { it.id }) { message -> MessageBubble(message.role, message.content, message.status) }
                state.streamProjection?.textFor(active.id)?.takeIf(String::isNotBlank)?.let { streamed ->
                    item { MessageBubble("assistant", streamed, "streaming") }
                }
                if (active.generating && !state.streaming) item { Text("Hermes 正在后台生成，正在恢复进度…") }
            }
            Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(input, { input = it }, label = { Text("给 Hermes 发消息") }, modifier = Modifier.weight(1f), maxLines = 4)
                if (state.streaming || active.generating) {
                    OutlinedButton(onClick = { scope.launch { state.stopHermes() } }, enabled = !state.stopping) { Text("停止") }
                } else {
                    Button(onClick = { if (state.beginHermes(input)) input = "" }, enabled = input.isNotBlank()) { Text("发送") }
                }
            }
            TextButton(onClick = { deleting = active }, enabled = !state.streaming, modifier = Modifier.padding(horizontal = 12.dp)) { Text("删除当前对话") }
        }
    }
    deleting?.let { conversation -> ConfirmDialog("删除对话", "确定删除会话「${conversation.title}」吗？", { deleting = null }) {
        deleting = null
        scope.launch { state.deleteConversation(conversation.id) }
    } }
}

@Composable
private fun MessageBubble(role: String, content: String, status: String) {
    val user = role == "user"
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (user) Arrangement.End else Arrangement.Start) {
        Surface(
            modifier = Modifier.fillMaxWidth(.88f),
            shape = MaterialTheme.shapes.medium,
            color = if (user) MaterialTheme.colorScheme.primary.copy(alpha = .15f) else MaterialTheme.colorScheme.surfaceVariant,
        ) {
            Column(Modifier.padding(12.dp)) {
                Text(if (user) "你" else "Hermes", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                Text(content)
                if (status == "interrupted") Text("已中断", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.error)
            }
        }
    }
}

@Composable
fun AdminScreen(state: OrbitState) {
    var server by remember(state.client.origin) { mutableStateOf(state.client.origin) }
    var deleteUser by remember { mutableStateOf<AdminUser?>(null) }
    var deleteAudit by remember { mutableStateOf<HermesConversation?>(null) }
    val scope = rememberCoroutineScope()
    Page {
        SectionTitle("管理中心", "用户、角色、审计与服务器设置") { TextButton(onClick = { scope.launch { state.loadAdmin() } }) { Text("刷新") } }
        Text("服务器地址", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        OutlinedTextField(server, { server = it }, modifier = Modifier.fillMaxWidth(), label = { Text("HTTPS 服务器地址") }, supportingText = { Text("保存后会退出登录；留空可恢复默认服务器") }, singleLine = true)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { state.changeServer(server.takeIf(String::isNotBlank)) }) { Text("保存并切换") }
            OutlinedButton(onClick = { server = BuildConfig.DEFAULT_SERVER; state.changeServer(null) }) { Text("恢复默认") }
        }
        HorizontalDivider()
        Text("用户（${state.adminUsers.size}）", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
        state.adminUsers.forEach { item ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Column { Text(item.username, fontWeight = FontWeight.Bold); Text(if (item.isBanned) "已封禁" else "正常", color = if (item.isBanned) MaterialTheme.colorScheme.error else Color(0xFF287A45)) }
                        Text(item.lastLoginAt.ifBlank { "尚未登录" }, style = MaterialTheme.typography.labelSmall)
                    }
                    state.roles.forEach { role ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(role.name in item.roles, { checked -> scope.launch { state.setUserRole(item, role.name, checked) } })
                            Column { Text(role.name); Text(role.description, style = MaterialTheme.typography.labelSmall) }
                        }
                    }
                    Row {
                        if (!item.isAdmin) {
                            TextButton(onClick = { scope.launch { state.setUserBanned(item, !item.isBanned) } }) { Text(if (item.isBanned) "解除封禁" else "封禁") }
                            TextButton(onClick = { deleteUser = item }) { Text("删除用户") }
                        }
                    }
                }
            }
        }
        Text("角色与权限", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
        val permissionLabels = state.permissions.associate { it.name to it.description }
        state.roles.forEach { role ->
            Text("${role.name}：${role.description}\n${role.permissions.joinToString("、") { permissionLabels[it] ?: it }}")
        }
        Text("Hermes 对话审计", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
        if (state.auditedConversations.isEmpty()) EmptyState("暂无对话记录") else state.auditedConversations.forEach { conversation ->
            Card(Modifier.fillMaxWidth().clickable { scope.launch { state.openAudit(conversation.id) } }) {
                Row(Modifier.fillMaxWidth().padding(14.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    Column(Modifier.weight(1f)) { Text(conversation.title, fontWeight = FontWeight.SemiBold); Text("${conversation.username} · ${conversation.updatedAt}", style = MaterialTheme.typography.labelSmall) }
                    TextButton(onClick = { deleteAudit = conversation }) { Text("删除") }
                }
            }
        }
    }
    state.auditedConversation?.let { conversation ->
        AlertDialog(
            onDismissRequest = { state.auditedConversation = null },
            confirmButton = { TextButton(onClick = { state.auditedConversation = null }) { Text("关闭") } },
            title = { Text("${conversation.username} · ${conversation.title}") },
            text = { LazyColumn(Modifier.height(420.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) { items(conversation.messages) { MessageBubble(it.role, it.content, it.status) } } },
        )
    }
    deleteUser?.let { item -> ConfirmDialog("删除账号", "确定删除账号「${item.username}」吗？此操作不可恢复。", { deleteUser = null }) {
        deleteUser = null
        scope.launch { state.deleteUser(item) }
    } }
    deleteAudit?.let { conversation -> ConfirmDialog("删除审计会话", "确定删除「${conversation.username}」的会话「${conversation.title}」吗？", { deleteAudit = null }) {
        deleteAudit = null
        scope.launch { state.deleteAudit(conversation.id) }
    } }
}

@Composable
fun HermesScreen(state: OrbitState) {
    val status = state.hermesStatus
    val scope = rememberCoroutineScope()
    var dashboard by remember { mutableStateOf(false) }
    Page {
        SectionTitle("Hermes 管理", "启动、停止并打开 Hermes 控制台") { TextButton(onClick = { scope.launch { state.loadHermesStatus() } }) { Text("刷新") } }
        if (status == null) EmptyState("正在读取 Hermes 状态") else {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Metric("已配置", if (status.configured) "是" else "否", Modifier.weight(1f))
                Metric("已安装", if (status.installed) "是" else "否", Modifier.weight(1f))
                Metric("运行中", if (status.running) "是" else "否", Modifier.weight(1f))
            }
            if (status.message.isNotBlank()) Text(status.message)
            if (status.details.isNotBlank()) Text(status.details, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { scope.launch { state.hermesAction("start") } }, enabled = !status.running) { Text("启动") }
                OutlinedButton(onClick = { scope.launch { state.hermesAction("stop") } }, enabled = status.running) { Text("停止") }
                Button(onClick = { dashboard = true }, enabled = status.running) { Text("打开控制台") }
            }
        }
    }
    if (dashboard && status != null) HermesDashboardDialog(state.client, status.dashboardPublicUrl, { dashboard = false })
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
private fun HermesDashboardDialog(client: OrbitClient, publicPath: String, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val base = remember(client.origin) { URI(client.origin) }
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize()) {
            Column {
                Row(Modifier.fillMaxWidth().padding(8.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text("Hermes 控制台", style = MaterialTheme.typography.titleLarge)
                    TextButton(onClick = onDismiss) { Text("关闭") }
                }
                AndroidView(
                    modifier = Modifier.fillMaxSize(),
                    factory = { webContext ->
                        CookieManager.getInstance().apply {
                            setAcceptCookie(true)
                            client.cookiePairs().forEach { setCookie(client.origin, it) }
                            flush()
                        }
                        WebView(webContext).apply {
                            settings.javaScriptEnabled = true
                            settings.domStorageEnabled = true
                            settings.allowFileAccess = false
                            settings.allowContentAccess = false
                            webViewClient = object : WebViewClient() {
                                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                                    val uri = request.url
                                    val internal = uri.host == base.host && uri.scheme == base.scheme && effectivePort(uri) == effectivePort(client.origin.toUri())
                                    if (!internal) runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, uri)) }
                                    return !internal
                                }
                            }
                            loadUrl(client.origin + "/" + publicPath.trimStart('/'))
                        }
                    },
                )
            }
        }
    }
}

private fun effectivePort(uri: Uri): Int = when { uri.port >= 0 -> uri.port; uri.scheme == "https" -> 443; else -> 80 }

@Composable
private fun ConfirmDialog(title: String, message: String, onDismiss: () -> Unit, onConfirm: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = { Button(onClick = onConfirm) { Text("确定") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
        title = { Text(title) },
        text = { Text(message) },
    )
}

@Composable
private fun OneFieldDialog(title: String, label: String, onDismiss: () -> Unit, onSubmit: (String) -> Unit) {
    var value by remember { mutableStateOf("") }
    AlertDialog(onDismissRequest = onDismiss, confirmButton = { Button(onClick = { onSubmit(value) }, enabled = value.isNotBlank()) { Text("保存") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } }, title = { Text(title) }, text = { OutlinedTextField(value, { value = it }, label = { Text(label) }, modifier = Modifier.fillMaxWidth()) })
}

@Composable
private fun BookmarkDialog(folders: List<Folder>, onDismiss: () -> Unit, onSubmit: (String, String, String, String) -> Unit) {
    var title by remember { mutableStateOf("") }; var url by remember { mutableStateOf("https://") }; var folder by remember { mutableStateOf(folders.firstOrNull()?.name.orEmpty()) }; var note by remember { mutableStateOf("") }
    FormDialog(
        title = "添加网站",
        onDismiss = onDismiss,
        valid = title.isNotBlank() && folder.isNotBlank(),
        onSubmit = { onSubmit(title, url, folder, note) },
    ) {
        OutlinedTextField(title, { title = it }, label = { Text("名称") }, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(url, { url = it }, label = { Text("网址") }, modifier = Modifier.fillMaxWidth())
        Text("收藏夹")
        LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) { items(folders) { item -> FilterChip(folder == item.name, { folder = item.name }, { Text(item.name) }) } }
        OutlinedTextField(note, { note = it }, label = { Text("备注") }, modifier = Modifier.fillMaxWidth())
    }
}

@Composable
private fun FolderDialog(folders: List<Folder>, selected: String, onDismiss: () -> Unit, onSelect: (String) -> Unit) {
    AlertDialog(onDismissRequest = onDismiss, confirmButton = { TextButton(onClick = onDismiss) { Text("取消") } }, title = { Text("移动到收藏夹") }, text = { LazyColumn { items(folders) { folder -> TextButton(onClick = { onSelect(folder.name) }, modifier = Modifier.fillMaxWidth()) { Text((if (folder.name == selected) "✓ " else "") + folder.name) } } } })
}

@Composable
private fun ExcerptDialog(item: Excerpt?, onDismiss: () -> Unit, onSubmit: (String, String, String, String, String) -> Unit) {
    var content by remember(item?.id) { mutableStateOf(item?.content.orEmpty()) }; var author by remember(item?.id) { mutableStateOf(item?.author.orEmpty()) }; var source by remember(item?.id) { mutableStateOf(item?.source.orEmpty()) }; var date by remember(item?.id) { mutableStateOf(item?.excerptDate?.ifBlank { LocalDate.now().toString() } ?: LocalDate.now().toString()) }; var note by remember(item?.id) { mutableStateOf(item?.note.orEmpty()) }
    FormDialog(if (item == null) "添加摘录" else "编辑摘录", onDismiss, content.isNotBlank(), { onSubmit(content, author, source, date, note) }) {
        OutlinedTextField(content, { content = it }, label = { Text("摘录内容") }, minLines = 4, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(author, { author = it }, label = { Text("作者") }, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(source, { source = it }, label = { Text("来源") }, modifier = Modifier.fillMaxWidth())
        DatePickerField("摘录日期", date, allowEmpty = false) { date = it }
        OutlinedTextField(note, { note = it }, label = { Text("备注") }, modifier = Modifier.fillMaxWidth())
    }
}

@Composable
private fun TodoDialog(onDismiss: () -> Unit, onSubmit: (String, String, String) -> Unit) {
    var title by remember { mutableStateOf("") }; var priority by remember { mutableStateOf("medium") }; var due by remember { mutableStateOf("") }
    FormDialog("添加待办", onDismiss, title.isNotBlank(), { onSubmit(title, priority, due) }) {
        OutlinedTextField(title, { title = it }, label = { Text("待办标题") }, modifier = Modifier.fillMaxWidth())
        LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) { items(listOf("low", "medium", "high")) { value -> FilterChip(priority == value, { priority = value }, { Text(priorityName(value)) }) } }
        DatePickerField("截止日期", due, allowEmpty = true) { due = it }
    }
}

@Composable
private fun PlanDialog(onDismiss: () -> Unit, onSubmit: (String, String, Int, String, String, String, Int, String) -> Unit) {
    var title by remember { mutableStateOf("") }; var frequency by remember { mutableStateOf("daily") }; var target by remember { mutableStateOf("1") }; var start by remember { mutableStateOf(LocalDate.now().toString()) }; var end by remember { mutableStateOf("") }; var time by remember { mutableStateOf("09:00") }; var duration by remember { mutableStateOf("30") }; var color by remember { mutableStateOf("violet") }
    FormDialog("添加计划", onDismiss, title.isNotBlank(), { onSubmit(title, frequency, target.toIntOrNull() ?: 1, start, end, time, duration.toIntOrNull() ?: 30, color) }) {
        OutlinedTextField(title, { title = it }, label = { Text("计划标题") }, modifier = Modifier.fillMaxWidth())
        LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) { items(listOf("daily", "weekly", "monthly")) { value -> FilterChip(frequency == value, { frequency = value }, { Text(frequencyName(value)) }) } }
        OutlinedTextField(target, { target = it.filter(Char::isDigit) }, label = { Text("每周期目标次数") }, modifier = Modifier.fillMaxWidth())
        DatePickerField("开始日期", start, allowEmpty = false) { start = it }
        DatePickerField("结束日期", end, allowEmpty = true) { end = it }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TimePickerField("提醒时间", time, Modifier.weight(1f)) { time = it }
            OutlinedTextField(duration, { duration = it.filter(Char::isDigit) }, label = { Text("分钟") }, modifier = Modifier.weight(1f))
        }
        LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) { items(listOf("violet", "orange", "green", "blue")) { value -> FilterChip(color == value, { color = value }, { Text(value) }) } }
    }
}

@Composable
private fun FormDialog(title: String, onDismiss: () -> Unit, valid: Boolean, onSubmit: () -> Unit, content: @Composable () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = { Button(onClick = onSubmit, enabled = valid) { Text("保存") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
        title = { Text(title) },
        text = { Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) { content() } },
    )
}

@Composable
private fun DatePickerField(label: String, value: String, allowEmpty: Boolean, onValueChange: (String) -> Unit) {
    val context = LocalContext.current
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        OutlinedButton(
            onClick = {
                val initial = runCatching { LocalDate.parse(value) }.getOrDefault(LocalDate.now())
                DatePickerDialog(
                    context,
                    { _, year, month, day -> onValueChange(LocalDate.of(year, month + 1, day).toString()) },
                    initial.year,
                    initial.monthValue - 1,
                    initial.dayOfMonth,
                ).show()
            },
            modifier = Modifier.weight(1f),
        ) { Text("$label：${value.ifBlank { "未设置" }}") }
        if (allowEmpty && value.isNotBlank()) TextButton(onClick = { onValueChange("") }) { Text("清除") }
    }
}

@Composable
private fun TimePickerField(label: String, value: String, modifier: Modifier = Modifier, onValueChange: (String) -> Unit) {
    val context = LocalContext.current
    OutlinedButton(
        onClick = {
            val initial = runCatching { LocalTime.parse(value) }.getOrDefault(LocalTime.of(9, 0))
            TimePickerDialog(
                context,
                { _, hour, minute -> onValueChange("%02d:%02d".format(hour, minute)) },
                initial.hour,
                initial.minute,
                true,
            ).show()
        },
        modifier = modifier,
    ) { Text("$label：$value") }
}

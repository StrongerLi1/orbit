package cloud.shawnstronger.orbit

import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.graphics.BitmapFactory
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AutoStories
import androidx.compose.material.icons.outlined.Download
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.Groups
import androidx.compose.material.icons.outlined.IosShare
import androidx.compose.material.icons.outlined.RateReview
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
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
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.LocalDate

@Composable
fun LibraryScreen(state: OrbitState) {
    val user = requireNotNull(state.user)
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var query by rememberSaveable { mutableStateOf(state.libraryQuery) }
    var filter by rememberSaveable { mutableStateOf("all") }
    var bookFormOpen by remember { mutableStateOf(false) }
    var editingBook by remember { mutableStateOf<LibraryBook?>(null) }
    var readTarget by remember { mutableStateOf<Pair<LibraryBook, LibraryRead?>?>(null) }
    var readersBook by remember { mutableStateOf<LibraryBook?>(null) }
    var reviewsBook by remember { mutableStateOf<LibraryBook?>(null) }
    var shareBook by remember { mutableStateOf<LibraryBook?>(null) }
    var deletingBook by remember { mutableStateOf<LibraryBook?>(null) }
    var deletingRead by remember { mutableStateOf<Pair<LibraryBook, LibraryRead>?>(null) }
    var deletingReview by remember { mutableStateOf<Pair<LibraryBook, LibraryReview>?>(null) }
    var shareAction by remember { mutableStateOf<String?>(null) }
    var pendingDownload by remember { mutableStateOf<LibraryBook?>(null) }
    var kindleSettingsOpen by remember { mutableStateOf(false) }

    val downloadLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val book = pendingDownload
        pendingDownload = null
        val uri = result.data?.data
        if (result.resultCode == Activity.RESULT_OK && book != null && uri != null) {
            scope.launch {
                state.downloadLibraryBook(book.id) {
                    context.contentResolver.openOutputStream(uri, "w") ?: error("无法写入所选文件")
                }
            }
        }
    }

    LaunchedEffect(query) {
        delay(250)
        if (query != state.libraryQuery) state.loadLibrary(query)
    }

    val visible = state.libraryBooks.filter { book ->
        when (filter) {
            "read" -> book.currentUserRead
            "unread" -> !book.currentUserRead
            else -> true
        }
    }

    LazyColumn(
        Modifier.fillMaxSize().padding(horizontal = 20.dp),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 18.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            SectionTitle("共享图书馆", "${visible.size} / ${state.libraryBooks.size} 本") {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = {
                        scope.launch { if (state.loadKindleSettings() != null) kindleSettingsOpen = true }
                    }) { Text("Kindle") }
                    if (user.can("library:upload")) Button(onClick = { editingBook = null; bookFormOpen = true }) { Text("上传") }
                }
            }
        }
        item {
            OutlinedTextField(
                value = query,
                onValueChange = { query = it.take(100) },
                label = { Text("搜索书名或作者") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
        }
        item {
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(filter == "all", { filter = "all" }, { Text("全部") })
                FilterChip(filter == "unread", { filter = "unread" }, { Text("我的未读") })
                FilterChip(filter == "read", { filter = "read" }, { Text("我的已读") })
            }
        }
        if (state.libraryLoading && state.libraryBooks.isNotEmpty()) {
            item {
                Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
                }
            }
        }
        state.libraryError?.let { message ->
            item {
                OrbitPanel(tonal = true) {
                    Text(message, color = MaterialTheme.colorScheme.error)
                    TextButton(onClick = { scope.launch { state.loadLibrary(query) } }) { Text("重试") }
                }
            }
        }
        state.kindleError?.let { message ->
            item { OrbitPanel(tonal = true) { Text(message, color = MaterialTheme.colorScheme.error) } }
        }
        if (state.kindleNotice.isNotBlank()) {
            item { OrbitPanel(tonal = true) { Text(state.kindleNotice, color = MaterialTheme.colorScheme.primary) } }
        }
        if (state.libraryLoading && state.libraryBooks.isEmpty()) {
            item { Box(Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() } }
        } else if (visible.isEmpty()) {
            item {
                EmptyState(
                    when {
                        state.libraryBooks.isNotEmpty() -> "这个分类还没有书"
                        query.isNotBlank() -> "没有匹配的书"
                        else -> "共享图书馆还没有书"
                    },
                )
            }
        } else {
            items(visible, key = LibraryBook::id) { book ->
                LibraryBookCard(
                    state = state,
                    book = book,
                    canManage = user.can("library:manage"),
                    onRead = { readTarget = book to null },
                    onReaders = {
                        readersBook = book
                        scope.launch { state.loadLibraryReaders(book.id) }
                    },
                    onReviews = {
                        reviewsBook = book
                        scope.launch { state.loadLibraryReviews(book.id) }
                    },
                    onDownload = {
                        pendingDownload = book
                        downloadLauncher.launch(
                            Intent(Intent.ACTION_CREATE_DOCUMENT)
                                .addCategory(Intent.CATEGORY_OPENABLE)
                                .setType(libraryMimeType(book.fileFormat))
                                .putExtra(Intent.EXTRA_TITLE, book.originalFilename),
                        )
                    },
                    onShare = {
                        shareBook = book
                        scope.launch { state.loadLibraryShare(book.id) }
                    },
                    onKindle = {
                        scope.launch {
                            val settings = state.kindleSettings ?: state.loadKindleSettings()
                            if (settings == null) return@launch
                            if (settings.kindleEmail.isBlank()) kindleSettingsOpen = true
                            else state.sendLibraryBookToKindle(book.id)
                        }
                    },
                    onEdit = { editingBook = book; bookFormOpen = true },
                    onDelete = { deletingBook = book },
                )
            }
        }
    }

    if (bookFormOpen) {
        LibraryBookDialog(
            item = editingBook,
            onDismiss = { bookFormOpen = false; editingBook = null },
            onSubmit = { title, author, bookFile, coverFile, removeCover ->
                scope.launch {
                    val success = editingBook?.let {
                        state.updateLibraryBook(it.id, title, author, removeCover, coverFile)
                    } ?: state.uploadLibraryBook(title, author, requireNotNull(bookFile), coverFile)
                    if (success) { bookFormOpen = false; editingBook = null }
                }
            },
        )
    }

    if (kindleSettingsOpen && state.kindleSettings != null) {
        KindleSettingsDialog(
            settings = requireNotNull(state.kindleSettings),
            onDismiss = { kindleSettingsOpen = false },
            onSave = { email -> scope.launch { if (state.saveKindleEmail(email)) kindleSettingsOpen = false } },
            onClear = {
                scope.launch {
                    if (state.clearKindleEmail()) {
                        kindleSettingsOpen = false
                    }
                }
            },
        )
    }

    readTarget?.let { (book, read) ->
        LibraryReadDialog(
            read = read,
            onDismiss = { readTarget = null },
            onSubmit = { date, review, anonymous ->
                scope.launch {
                    val success = if (read == null) state.createLibraryRead(book.id, date, review, anonymous)
                    else state.updateLibraryRead(book.id, read.id, date)
                    if (success) {
                        readTarget = null
                        if (read != null) readersBook = book
                    }
                }
            },
        )
    }

    readersBook?.let { book ->
        LibraryReadersDialog(
            book = book,
            readers = state.libraryReaders,
            onDismiss = { readersBook = null; state.clearLibraryDetail() },
            onEdit = { read -> readersBook = null; readTarget = book to read },
            onDelete = { read -> deletingRead = book to read },
        )
    }

    reviewsBook?.let { book ->
        LibraryReviewsDialog(
            book = book,
            reviews = state.libraryReviews,
            onDismiss = { reviewsBook = null; state.clearLibraryDetail() },
            onCreate = { content, anonymous -> state.createLibraryReview(book.id, content, anonymous) },
            onToggle = { review -> scope.launch { state.toggleLibraryReview(book.id, review) } },
            onDelete = { review -> deletingReview = book to review },
        )
    }

    shareBook?.let { book ->
        val url = state.librarySharePath.takeIf(String::isNotBlank)?.let { runCatching { libraryShareUrl(state.client.origin, it) }.getOrNull() }.orEmpty()
        LibraryShareDialog(
            book = book,
            url = url,
            canManage = user.can("library:manage"),
            onDismiss = { shareBook = null; state.clearLibraryDetail() },
            onCopy = {
                context.getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText("Orbit 电子书分享", url))
            },
            onShare = {
                context.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, url), "分享电子书"))
            },
            onRegenerate = { shareAction = "regenerate" },
            onRevoke = { shareAction = "revoke" },
        )
    }

    shareAction?.let { action ->
        val book = shareBook
        if (book != null) {
            ConfirmDialog(
                if (action == "regenerate") "重新生成分享链接" else "撤销分享链接",
                if (action == "regenerate") "旧链接会立即失效，确定继续吗？" else "当前公开下载链接会立即失效，确定继续吗？",
                { shareAction = null },
            ) {
                shareAction = null
                scope.launch {
                    if (action == "regenerate") state.loadLibraryShare(book.id, regenerate = true)
                    else if (state.revokeLibraryShare(book.id)) { shareBook = null; state.clearLibraryDetail() }
                }
            }
        }
    }

    deletingBook?.let { book ->
        ConfirmDialog(
            "删除《${book.title}》",
            "将同时删除电子书、封面、${book.readCount} 条阅读记录和全部书评。此操作不可撤销。",
            { deletingBook = null },
        ) { deletingBook = null; scope.launch { state.deleteLibraryBook(book.id) } }
    }
    deletingRead?.let { (book, read) ->
        ConfirmDialog("删除阅读记录", "确定删除 ${read.readDate} 的阅读记录吗？独立书评不会被删除。", { deletingRead = null }) {
            deletingRead = null
            scope.launch { state.deleteLibraryRead(book.id, read.id) }
        }
    }
    deletingReview?.let { (book, review) ->
        ConfirmDialog("删除书评", "确定删除这条书评吗？", { deletingReview = null }) {
            deletingReview = null
            scope.launch { state.deleteLibraryReview(book.id, review) }
        }
    }
}

@Composable
private fun LibraryBookCard(
    state: OrbitState,
    book: LibraryBook,
    canManage: Boolean,
    onRead: () -> Unit,
    onReaders: () -> Unit,
    onReviews: () -> Unit,
    onDownload: () -> Unit,
    onShare: () -> Unit,
    onKindle: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
) {
    var cover by remember(book.id, book.updatedAt) { mutableStateOf<androidx.compose.ui.graphics.ImageBitmap?>(null) }
    LaunchedEffect(book.id, book.updatedAt, book.hasCover) {
        cover = if (!book.hasCover) null else state.libraryCover(book.id)?.let { bytes ->
            withContext(Dispatchers.Default) { BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap() }
        }
    }
    OrbitPanel {
        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            Surface(
                modifier = Modifier.width(92.dp).aspectRatio(.72f),
                shape = RoundedCornerShape(10.dp),
                color = MaterialTheme.colorScheme.primaryContainer,
            ) {
                if (cover != null) Image(cover!!, book.title, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
                else Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(book.title.firstOrNull()?.toString() ?: "书", style = MaterialTheme.typography.headlineLarge, color = MaterialTheme.colorScheme.onPrimaryContainer)
                }
            }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(book.title, style = MaterialTheme.typography.titleLarge, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Text(book.author, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("${book.fileFormat.uppercase()} · ${formatLibraryFileSize(book.fileSize)}", style = MaterialTheme.typography.labelMedium)
                Text("${if (book.currentUserRead) "已读 ${book.currentUserReadCount} 次" else "未读"} · ${book.readerCount} 人 / ${book.readCount} 次", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelMedium)
                Text("${book.uploadedByName} 上传", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
            TextButton(onClick = onRead) { Icon(Icons.Outlined.AutoStories, null); Text("记录") }
            TextButton(onClick = onReaders) { Icon(Icons.Outlined.Groups, null); Text("读者") }
            TextButton(onClick = onReviews) { Icon(Icons.Outlined.RateReview, null); Text("书评") }
            TextButton(onClick = onDownload) { Icon(Icons.Outlined.Download, null); Text("下载") }
            TextButton(onClick = onShare) { Icon(Icons.Outlined.IosShare, null); Text("分享") }
            if (book.canSendToKindle) {
                TextButton(onClick = onKindle, enabled = state.kindleSendingBookId == null) {
                    Text(if (state.kindleSendingBookId == book.id) "发送中…" else "发到 Kindle")
                }
            }
        }
        if (canManage) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                TextButton(onClick = onEdit) { Icon(Icons.Outlined.Edit, null); Text("编辑") }
                TextButton(onClick = onDelete) { Text("删除", color = MaterialTheme.colorScheme.error) }
            }
        }
    }
}

@Composable
private fun KindleSettingsDialog(
    settings: KindleSettings,
    onDismiss: () -> Unit,
    onSave: (String) -> Unit,
    onClear: () -> Unit,
) {
    var email by remember(settings.kindleEmail) { mutableStateOf(settings.kindleEmail) }
    val valid = Regex("^[^@\\s]+@kindle\\.com$", RegexOption.IGNORE_CASE).matches(email.trim())
    FormDialog("Kindle 邮箱设置", onDismiss, valid, { onSave(email.trim()) }) {
        OutlinedTextField(
            email,
            { email = it.take(320) },
            label = { Text("你的 Kindle 邮箱") },
            placeholder = { Text("name@kindle.com") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Text(
            if (settings.enabled) "请先把 ${settings.senderEmail} 加入 Amazon 的已认可发件人列表。支持 EPUB、PDF、TXT，附件上限 ${settings.maxAttachmentMb} MB。"
            else "服务器尚未配置邮件发送服务。你可以先保存邮箱，再联系管理员配置 SMTP。",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (settings.kindleEmail.isNotBlank()) {
            TextButton(onClick = onClear) { Text("清除 Kindle 邮箱", color = MaterialTheme.colorScheme.error) }
        }
    }
}

@Composable
private fun LibraryBookDialog(
    item: LibraryBook?,
    onDismiss: () -> Unit,
    onSubmit: (String, String, LibraryUploadFile?, LibraryUploadFile?, Boolean) -> Unit,
) {
    val context = LocalContext.current
    var title by remember(item?.id) { mutableStateOf(item?.title.orEmpty()) }
    var author by remember(item?.id) { mutableStateOf(item?.author.orEmpty()) }
    var titleManual by remember(item?.id) { mutableStateOf(item != null) }
    var authorManual by remember(item?.id) { mutableStateOf(item != null) }
    var bookUri by remember(item?.id) { mutableStateOf<Uri?>(null) }
    var coverUri by remember(item?.id) { mutableStateOf<Uri?>(null) }
    var bookName by remember(item?.id) { mutableStateOf("") }
    var coverName by remember(item?.id) { mutableStateOf("") }
    var removeCover by remember(item?.id) { mutableStateOf(false) }
    var localError by remember(item?.id) { mutableStateOf("") }
    val bookPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            val name = documentName(context, uri)
            if (!isSupportedLibraryBook(name)) {
                bookUri = null
                bookName = ""
                localError = "请选择 EPUB、PDF、MOBI、AZW3 或 TXT 文件"
            }
            else {
                bookUri = uri
                bookName = name
                localError = ""
                val metadata = libraryMetadataFromFilename(name)
                if (!titleManual) title = metadata.title
                if (!authorManual) author = metadata.author
            }
        }
    }
    val coverPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) { coverUri = uri; coverName = documentName(context, uri); removeCover = false }
    }
    FormDialog(
        if (item == null) "上传电子书" else "编辑《${item.title}》",
        onDismiss,
        valid = if (item == null) bookUri != null else title.isNotBlank() && author.isNotBlank(),
        onSubmit = {
            onSubmit(
                if (item == null && !titleManual) "" else title.trim(),
                if (item == null && !authorManual) "" else author.trim(),
                bookUri?.let { uploadFile(context, it, bookName) },
                coverUri?.let { uploadFile(context, it, coverName) },
                removeCover,
            )
        },
    ) {
        if (item == null) {
            OutlinedButton(onClick = { bookPicker.launch(arrayOf("*/*")) }, modifier = Modifier.fillMaxWidth()) {
                Text(bookName.ifBlank { "选择电子书" }, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        OutlinedTextField(title, { title = it.take(300); titleManual = true }, label = { Text("书名") }, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(author, { author = it.take(200); authorManual = true }, label = { Text("作者") }, modifier = Modifier.fillMaxWidth())
        if (item == null && bookUri != null) Text("未手动修改的预填值不会覆盖文件内元数据。", style = MaterialTheme.typography.bodySmall)
        OutlinedButton(onClick = { coverPicker.launch(arrayOf("image/jpeg", "image/png", "image/webp")) }, modifier = Modifier.fillMaxWidth()) {
            Text(coverName.ifBlank { if (item?.hasCover == true) "替换封面（可选）" else "选择封面（可选）" }, maxLines = 1)
        }
        if (item?.hasCover == true && coverUri == null) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(removeCover, { removeCover = it })
                Text("移除现有封面")
            }
        }
        if (localError.isNotBlank()) Text(localError, color = MaterialTheme.colorScheme.error)
        if (item == null) Text("支持格式最大 100 MB；服务器会校验内容并提取可用元数据。", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun LibraryReadDialog(read: LibraryRead?, onDismiss: () -> Unit, onSubmit: (String, String, Boolean) -> Unit) {
    var date by remember(read?.id) { mutableStateOf(read?.readDate ?: LocalDate.now().toString()) }
    var review by remember(read?.id) { mutableStateOf("") }
    var anonymous by remember(read?.id) { mutableStateOf(false) }
    FormDialog(if (read == null) "记录一次阅读" else "修改阅读日期", onDismiss, date.isNotBlank() && review.length <= 3000, { onSubmit(date, review.trim(), anonymous) }) {
        DatePickerField("阅读日期", date, allowEmpty = false) { date = it }
        if (read == null) {
            OutlinedTextField(review, { review = it.take(3000) }, label = { Text("书评（可选）") }, minLines = 3, modifier = Modifier.fillMaxWidth())
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(!anonymous, { anonymous = false }, { Text("实名") })
                FilterChip(anonymous, { anonymous = true }, { Text("匿名") })
            }
        }
    }
}

@Composable
private fun LibraryReadersDialog(
    book: LibraryBook,
    readers: LibraryReaders?,
    onDismiss: () -> Unit,
    onEdit: (LibraryRead) -> Unit,
    onDelete: (LibraryRead) -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
        title = { Text("《${book.title}》的阅读记录") },
        text = {
            Column(Modifier.heightIn(max = 520.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (readers == null) CircularProgressIndicator()
                else if (readers.readers.isEmpty()) Text("还没有阅读记录")
                else readers.readers.forEach { reader ->
                    Text("${reader.username} · ${reader.reads.size} 次", fontWeight = FontWeight.Bold)
                    reader.reads.forEach { read ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(read.readDate, modifier = Modifier.weight(1f))
                            if (reader.isCurrentUser) {
                                TextButton(onClick = { onEdit(read) }) { Text("修改") }
                                TextButton(onClick = { onDelete(read) }) { Text("删除") }
                            }
                        }
                    }
                    HorizontalDivider()
                }
            }
        },
    )
}

@Composable
private fun LibraryReviewsDialog(
    book: LibraryBook,
    reviews: List<LibraryReview>?,
    onDismiss: () -> Unit,
    onCreate: suspend (String, Boolean) -> Boolean,
    onToggle: (LibraryReview) -> Unit,
    onDelete: (LibraryReview) -> Unit,
) {
    var content by remember(book.id) { mutableStateOf("") }
    var anonymous by remember(book.id) { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
        title = { Text("《${book.title}》的书评") },
        text = {
            Column(Modifier.heightIn(max = 560.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedTextField(content, { content = it.take(3000) }, label = { Text("写一条书评") }, minLines = 3, modifier = Modifier.fillMaxWidth())
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Row(Modifier.weight(1f), verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(anonymous, { anonymous = it })
                        Text("匿名发布")
                    }
                    Button(onClick = { scope.launch { if (onCreate(content.trim(), anonymous)) content = "" } }, enabled = content.isNotBlank()) {
                        Text("发布")
                    }
                }
                HorizontalDivider()
                if (reviews == null) CircularProgressIndicator()
                else if (reviews.isEmpty()) Text("还没有书评")
                reviews.orEmpty().forEach { review ->
                    Text(review.username, fontWeight = FontWeight.Bold)
                    Text(review.content)
                    Text(review.createdAt, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (review.canToggleAnonymous || review.canDelete) {
                        Row {
                            if (review.canToggleAnonymous) TextButton(onClick = { onToggle(review) }) { Text(if (review.isAnonymous) "取消匿名" else "设为匿名") }
                            if (review.canDelete) TextButton(onClick = { onDelete(review) }) { Text("删除") }
                        }
                    }
                    HorizontalDivider()
                }
            }
        },
    )
}

@Composable
private fun LibraryShareDialog(
    book: LibraryBook,
    url: String,
    canManage: Boolean,
    onDismiss: () -> Unit,
    onCopy: () -> Unit,
    onShare: () -> Unit,
    onRegenerate: () -> Unit,
    onRevoke: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
        title = { Text("分享《${book.title}》") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (url.isBlank()) CircularProgressIndicator() else {
                    OutlinedTextField(url, {}, readOnly = true, label = { Text("公开下载链接") }, modifier = Modifier.fillMaxWidth())
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = onCopy) { Text("复制") }
                        Button(onClick = onShare) { Text("系统分享") }
                    }
                    Text("任何拿到链接的人都能下载，请只发给信任的人。", style = MaterialTheme.typography.bodySmall)
                    if (canManage) {
                        HorizontalDivider()
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(onClick = onRegenerate) { Text("重新生成") }
                            TextButton(onClick = onRevoke) { Text("撤销分享", color = MaterialTheme.colorScheme.error) }
                        }
                    }
                }
            }
        },
    )
}

private fun documentName(context: Context, uri: Uri): String {
    context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
        if (cursor.moveToFirst()) return cursor.getString(0).orEmpty()
    }
    return uri.lastPathSegment?.substringAfterLast('/') ?: "file"
}

private fun uploadFile(context: Context, uri: Uri, filename: String) = LibraryUploadFile(
    filename = filename,
    contentType = context.contentResolver.getType(uri).orEmpty().ifBlank { libraryMimeType(libraryBookExtension(filename)) },
    openStream = { context.contentResolver.openInputStream(uri) ?: error("无法读取所选文件") },
)

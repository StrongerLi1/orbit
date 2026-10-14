package cloud.shawnstronger.orbit

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

private val diaryDateTimeFormatter = DateTimeFormatter.ofPattern("yyyy年M月d日 HH:mm", Locale.SIMPLIFIED_CHINESE)

@Composable
fun WritingsScreen(state: OrbitState) {
    val canWrite = state.user?.can("content:write") == true
    val scope = rememberCoroutineScope()
    var adding by remember { mutableStateOf(false) }
    var editing by remember { mutableStateOf<WritingPost?>(null) }
    var deleting by remember { mutableStateOf<WritingPost?>(null) }

    Page {
        SectionTitle("写点什么", "日记、短句，或想留给自己的话") {
            if (canWrite) Button(onClick = { adding = true }) { Text("写一点") }
        }
        if (state.writings.isEmpty()) EmptyState("还没有写下任何内容")
        state.writings.forEach { item ->
            OrbitPanel {
                Text(item.content, style = MaterialTheme.typography.bodyLarge)
                Text(
                    "${if (item.visibility == "public") "公开" else "仅自己可见"} · ${if (item.isAnonymous) "匿名" else "实名"}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(
                    "${item.createdByName} · ${formatApiDateTime(item.updatedAt)}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (canWrite && item.canManage) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        TextButton(onClick = { editing = item }) { Text("编辑") }
                        TextButton(onClick = { deleting = item }) { Text("删除") }
                    }
                }
            }
        }
    }

    if (adding || editing != null) {
        WritingDialog(editing, onDismiss = { adding = false; editing = null }) { content, visibility, anonymous ->
            scope.launch {
                val success = editing?.let { state.updateWriting(it.id, content, visibility, anonymous) }
                    ?: state.addWriting(content, visibility, anonymous)
                if (success) { adding = false; editing = null }
            }
        }
    }
    deleting?.let { item ->
        ConfirmDialog("删除内容", "确定删除这段内容吗？此操作不可恢复。", { deleting = null }) {
            deleting = null
            scope.launch { state.deleteContent("writings", item.id) }
        }
    }
}

@Composable
private fun WritingDialog(item: WritingPost?, onDismiss: () -> Unit, onSubmit: (String, String, Boolean) -> Unit) {
    var content by remember(item?.id) { mutableStateOf(item?.content.orEmpty()) }
    var visibility by remember(item?.id) { mutableStateOf(item?.visibility ?: "private") }
    var anonymous by remember(item?.id) { mutableStateOf(item?.isAnonymous ?: false) }
    FormDialog(
        title = if (item == null) "写点什么" else "编辑内容",
        onDismiss = onDismiss,
        valid = content.isNotBlank(),
        onSubmit = { onSubmit(content.trim(), visibility, anonymous) },
    ) {
        OutlinedTextField(
            value = content,
            onValueChange = { content = it.take(8000) },
            label = { Text("内容") },
            supportingText = { Text("${content.length}/8000") },
            minLines = 6,
            modifier = Modifier.fillMaxWidth(),
        )
        Text("谁可以看到")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(visibility == "private", { visibility = "private" }, { Text("仅自己") })
            FilterChip(visibility == "public", { visibility = "public" }, { Text("公开") })
        }
        Text("署名方式")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(!anonymous, { anonymous = false }, { Text("实名") })
            FilterChip(anonymous, { anonymous = true }, { Text("匿名") })
        }
    }
}

@Composable
fun FilmDiaryScreen(state: OrbitState) {
    val canWrite = state.user?.can("content:write") == true
    val scope = rememberCoroutineScope()
    var addingRoll by remember { mutableStateOf(false) }
    var editingRoll by remember { mutableStateOf<FilmRoll?>(null) }
    var deletingRoll by remember { mutableStateOf<FilmRoll?>(null) }
    var exposureRoll by remember { mutableStateOf<FilmRoll?>(null) }
    var editingExposure by remember { mutableStateOf<FilmExposure?>(null) }
    var deletingExposure by remember { mutableStateOf<FilmExposure?>(null) }

    Page {
        SectionTitle("胶片日记", "记住每一次按下快门") {
            if (canWrite) Button(onClick = { addingRoll = true }) { Text("新建胶卷") }
        }
        if (state.filmRolls.isEmpty()) EmptyState("还没有胶卷，先装入第一卷吧")
        listOf("active" to "拍摄中", "finished" to "已拍完").forEach { (status, label) ->
            val rolls = state.filmRolls.filter { it.status == status }
            if (rolls.isNotEmpty()) {
                SectionTitle(label, "${rolls.size} 卷")
                rolls.forEach { roll ->
                    FilmRollCard(
                        roll = roll,
                        canWrite = canWrite,
                        onAddExposure = { exposureRoll = roll; editingExposure = null },
                        onEditRoll = { editingRoll = roll },
                        onToggleStatus = {
                            scope.launch { state.updateFilmRollStatus(roll, if (roll.status == "active") "finished" else "active") }
                        },
                        onDeleteRoll = { deletingRoll = roll },
                        onEditExposure = { exposureRoll = roll; editingExposure = it },
                        onDeleteExposure = { deletingExposure = it },
                    )
                }
            }
        }
    }

    if (addingRoll || editingRoll != null) {
        FilmRollDialog(editingRoll, { addingRoll = false; editingRoll = null }) { stock, iso, camera, status ->
            scope.launch {
                val success = editingRoll?.let { state.updateFilmRoll(it.id, stock, iso, camera, status) }
                    ?: state.addFilmRoll(stock, iso, camera, status)
                if (success) { addingRoll = false; editingRoll = null }
            }
        }
    }
    exposureRoll?.let { roll ->
        FilmExposureDialog(roll, editingExposure, { exposureRoll = null; editingExposure = null }) { frame, takenAt, location, thoughts, lens, aperture, shutter ->
            scope.launch {
                val success = editingExposure?.let {
                    state.updateFilmExposure(it, frame, takenAt, location, thoughts, lens, aperture, shutter)
                } ?: state.addFilmExposure(roll.id, frame, takenAt, location, thoughts, lens, aperture, shutter)
                if (success) { exposureRoll = null; editingExposure = null }
            }
        }
    }
    deletingRoll?.let { roll ->
        val detail = if (roll.exposures.isEmpty()) "确定删除「${roll.filmStock}」吗？" else
            "确定删除「${roll.filmStock}」吗？其中 ${roll.exposures.size} 条曝光记录也会一起删除。"
        ConfirmDialog("删除胶卷", detail, { deletingRoll = null }) {
            deletingRoll = null
            scope.launch { state.deleteContent("film-rolls", roll.id) }
        }
    }
    deletingExposure?.let { exposure ->
        ConfirmDialog("删除曝光记录", "确定删除第 ${exposure.frameNumber} 格的记录吗？", { deletingExposure = null }) {
            deletingExposure = null
            scope.launch { state.deleteFilmExposure(exposure) }
        }
    }
}

@Composable
private fun FilmRollCard(
    roll: FilmRoll,
    canWrite: Boolean,
    onAddExposure: () -> Unit,
    onEditRoll: () -> Unit,
    onToggleStatus: () -> Unit,
    onDeleteRoll: () -> Unit,
    onEditExposure: (FilmExposure) -> Unit,
    onDeleteExposure: (FilmExposure) -> Unit,
) {
    OrbitPanel(tonal = roll.status == "active") {
        Text(roll.filmStock, style = MaterialTheme.typography.titleLarge)
        Text(
            listOf(roll.camera, roll.iso?.let { "ISO $it" }).filterNotNull().joinToString(" · "),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (roll.exposures.isEmpty()) Text("还没有曝光记录", color = MaterialTheme.colorScheme.onSurfaceVariant)
        roll.exposures.forEach { exposure ->
            Surface(
                color = MaterialTheme.colorScheme.surface,
                shape = MaterialTheme.shapes.small,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Text("第 ${exposure.frameNumber} 格 · ${formatApiDateTime(exposure.takenAt)}", style = MaterialTheme.typography.titleSmall)
                    if (exposure.location.isNotBlank()) Text(exposure.location, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (exposure.thoughts.isNotBlank()) Text(exposure.thoughts)
                    val settings = listOf(exposure.lens, exposure.aperture, exposure.shutterSpeed).filter(String::isNotBlank)
                    if (settings.isNotEmpty()) Text(settings.joinToString(" · "), style = MaterialTheme.typography.labelMedium)
                    if (canWrite) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        TextButton(onClick = { onEditExposure(exposure) }) { Text("编辑") }
                        TextButton(onClick = { onDeleteExposure(exposure) }) { Text("删除") }
                    }
                }
            }
        }
        if (canWrite) {
            OutlinedButton(onClick = onAddExposure, modifier = Modifier.fillMaxWidth()) { Text("记录一次曝光") }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                TextButton(onClick = onToggleStatus) { Text(if (roll.status == "active") "标记拍完" else "继续拍摄") }
                TextButton(onClick = onEditRoll) { Text("编辑") }
                TextButton(onClick = onDeleteRoll) { Text("删除") }
            }
        }
    }
}

@Composable
private fun FilmRollDialog(item: FilmRoll?, onDismiss: () -> Unit, onSubmit: (String, Int?, String, String) -> Unit) {
    var stock by remember(item?.id) { mutableStateOf(item?.filmStock.orEmpty()) }
    var camera by remember(item?.id) { mutableStateOf(item?.camera.orEmpty()) }
    var iso by remember(item?.id) { mutableStateOf(item?.iso?.toString().orEmpty()) }
    var status by remember(item?.id) { mutableStateOf(item?.status ?: "active") }
    val isoValue = iso.toIntOrNull()
    val validIso = iso.isBlank() || (isoValue != null && isoValue in 1..25_600)
    FormDialog(if (item == null) "新建胶卷" else "编辑胶卷", onDismiss, stock.isNotBlank() && camera.isNotBlank() && validIso, {
        onSubmit(stock.trim(), isoValue, camera.trim(), status)
    }) {
        OutlinedTextField(stock, { stock = it.take(160) }, label = { Text("胶卷名称 / 型号") }, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(camera, { camera = it.take(160) }, label = { Text("相机") }, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(
            iso,
            { iso = it.filter(Char::isDigit).take(5) },
            label = { Text("ISO（可选）") },
            isError = !validIso,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            modifier = Modifier.fillMaxWidth(),
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(status == "active", { status = "active" }, { Text("拍摄中") })
            FilterChip(status == "finished", { status = "finished" }, { Text("已拍完") })
        }
    }
}

@Composable
private fun FilmExposureDialog(
    roll: FilmRoll,
    item: FilmExposure?,
    onDismiss: () -> Unit,
    onSubmit: (Int, String, String, String, String, String, String) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val initial = remember(item?.id) {
        item?.takenAt?.let { runCatching { filmLocalDateTime(it) }.getOrNull() } ?: java.time.LocalDateTime.now()
    }
    var frame by remember(item?.id, roll.id) { mutableStateOf((item?.frameNumber ?: nextFilmFrame(roll.exposures)).toString()) }
    var date by remember(item?.id) { mutableStateOf(initial.toLocalDate().toString()) }
    var time by remember(item?.id) { mutableStateOf(initial.toLocalTime().withSecond(0).withNano(0).toString()) }
    var location by remember(item?.id) { mutableStateOf(item?.location.orEmpty()) }
    var thoughts by remember(item?.id) { mutableStateOf(item?.thoughts.orEmpty()) }
    var lens by remember(item?.id) { mutableStateOf(item?.lens.orEmpty()) }
    var aperture by remember(item?.id) { mutableStateOf(item?.aperture.orEmpty()) }
    var shutter by remember(item?.id) { mutableStateOf(item?.shutterSpeed.orEmpty()) }
    var locating by remember { mutableStateOf(false) }
    var locationHint by remember { mutableStateOf<String?>(null) }

    fun locate() {
        locating = true
        locationHint = null
        scope.launch {
            val address = currentReadableAddress(context)
            if (address != null) {
                location = address.take(300)
                locationHint = "已填入当前位置，可继续修改"
            } else {
                locationHint = "无法解析当前位置，请手动填写"
            }
            locating = false
        }
    }

    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        if (result.values.any { it }) locate() else locationHint = "未获得定位权限，请手动填写"
    }
    val frameValue = frame.toIntOrNull()
    val valid = frameValue != null && frameValue in 0..999 && runCatching { LocalDate.parse(date); LocalTime.parse(time) }.isSuccess

    FormDialog(if (item == null) "记录一次曝光" else "编辑曝光记录", onDismiss, valid, {
        val takenAt = filmInstant(LocalDate.parse(date), LocalTime.parse(time))
        onSubmit(frameValue!!, takenAt, location.trim(), thoughts.trim(), lens.trim(), aperture.trim(), shutter.trim())
    }) {
        OutlinedTextField(
            frame,
            { frame = it.filter(Char::isDigit).take(3) },
            label = { Text("画幅序号") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            modifier = Modifier.fillMaxWidth(),
        )
        DatePickerField("拍摄日期", date, allowEmpty = false) { date = it }
        TimePickerField("拍摄时间", time, Modifier.fillMaxWidth()) { time = it }
        OutlinedTextField(location, { location = it.take(300) }, label = { Text("地点（可选）") }, modifier = Modifier.fillMaxWidth())
        OutlinedButton(
            enabled = !locating,
            onClick = {
                val granted = listOf(Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION).any {
                    ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED
                }
                if (granted) locate() else permissionLauncher.launch(
                    arrayOf(Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION),
                )
            },
            modifier = Modifier.fillMaxWidth(),
        ) { Text(if (locating) "正在定位…" else "获取当前位置") }
        locationHint?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        OutlinedTextField(thoughts, { thoughts = it.take(3000) }, label = { Text("当时的想法（可选）") }, minLines = 3, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(lens, { lens = it.take(160) }, label = { Text("镜头（可选）") }, modifier = Modifier.fillMaxWidth())
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(aperture, { aperture = it.take(40) }, label = { Text("光圈") }, modifier = Modifier.weight(1f))
            OutlinedTextField(shutter, { shutter = it.take(40) }, label = { Text("快门速度") }, modifier = Modifier.weight(1f))
        }
    }
}

private fun formatApiDateTime(value: String): String = runCatching {
    Instant.parse(value).atZone(ZoneId.systemDefault()).format(diaryDateTimeFormatter)
}.getOrDefault(value)

package cloud.shawnstronger.orbit

import android.annotation.SuppressLint
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { OrbitTheme { OrbitApplication() } }
    }
}

private val OrbitColors = lightColorScheme(
    primary = Color(0xFF6D5BD0),
    onPrimary = Color.White,
    secondary = Color(0xFF876F50),
    background = Color(0xFFF7F6F2),
    surface = Color(0xFFFFFDF8),
    surfaceVariant = Color(0xFFECE9E2),
    error = Color(0xFFB3261E),
)

@Composable
fun OrbitTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = OrbitColors, content = content)
}

enum class OrbitRoute(val label: String, val permission: String? = null) {
    Dashboard("概览", "content:read"),
    Bookmarks("收藏夹", "content:read"),
    Excerpts("摘录", "content:read"),
    Plans("日常计划", "content:read"),
    Todos("待办事项", "content:read"),
    Netdisk("网盘搜索", "netdisk:search"),
    Chat("Hermes 聊天", "hermes:chat"),
    Admin("用户管理", "users:manage"),
    Hermes("Hermes 管理", "agents:manage"),
}

@Composable
private fun OrbitApplication() {
    val context = LocalContext.current
    val client = remember { OrbitClient(context.applicationContext) }
    val state = remember { OrbitState(client) }
    var route by remember { mutableStateOf(OrbitRoute.Dashboard) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) { state.bootstrap() }
    DisposableEffect(Unit) { onDispose { state.close() } }

    state.error?.let { message ->
        AlertDialog(
            onDismissRequest = state::dismissError,
            confirmButton = { TextButton(onClick = state::dismissError) { Text("知道了") } },
            title = { Text("Orbit") },
            text = { Text(message) },
        )
    }

    when {
        state.bootstrapping -> LoadingScreen("正在恢复登录状态…")
        state.user == null -> AuthScreen(state)
        else -> AppShell(
            state = state,
            route = route,
            onRoute = { route = it },
            onLogout = { scope.launch { state.logout() } },
        )
    }
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun AppShell(
    state: OrbitState,
    route: OrbitRoute,
    onRoute: (OrbitRoute) -> Unit,
    onLogout: () -> Unit,
) {
    val user = requireNotNull(state.user)
    val destinations = OrbitRoute.entries.filter { it.permission == null || user.can(it.permission) }
    var searchOpen by remember { mutableStateOf(false) }
    var searchQuery by remember { mutableStateOf(state.bookmarkSearch) }

    LaunchedEffect(route) {
        when (route) {
            OrbitRoute.Chat -> state.loadConversations()
            OrbitRoute.Admin -> state.loadAdmin()
            OrbitRoute.Hermes -> state.loadHermesStatus()
            else -> Unit
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Orbit · ${route.label}", fontWeight = FontWeight.SemiBold) },
                actions = {
                    TextButton(onClick = { searchOpen = true }) { Text("搜索") }
                    Text(user.username + if (user.isAdmin) " · 管理员" else "", style = MaterialTheme.typography.labelMedium)
                    TextButton(onClick = onLogout) { Text("退出") }
                },
            )
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            LazyRow(
                modifier = Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surface).padding(horizontal = 12.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(destinations) { destination ->
                    FilterChip(
                        selected = route == destination,
                        onClick = { onRoute(destination) },
                        label = { Text(destination.label) },
                    )
                }
            }
            Box(Modifier.fillMaxSize()) {
                when (route) {
                    OrbitRoute.Dashboard -> DashboardScreen(state, onRoute)
                    OrbitRoute.Bookmarks -> BookmarksScreen(state)
                    OrbitRoute.Excerpts -> ExcerptsScreen(state)
                    OrbitRoute.Plans -> PlansScreen(state)
                    OrbitRoute.Todos -> TodosScreen(state)
                    OrbitRoute.Netdisk -> NetdiskScreen(state)
                    OrbitRoute.Chat -> HermesChatScreen(state)
                    OrbitRoute.Admin -> AdminScreen(state)
                    OrbitRoute.Hermes -> HermesScreen(state)
                }
                if (state.busy) {
                    Box(Modifier.fillMaxSize().background(Color.White.copy(alpha = 0.55f)), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
            }
        }
    }
    if (searchOpen) {
        AlertDialog(
            onDismissRequest = { searchOpen = false },
            confirmButton = {
                Button(onClick = {
                    state.bookmarkSearch = searchQuery
                    searchOpen = false
                    onRoute(OrbitRoute.Bookmarks)
                }) { Text("搜索收藏") }
            },
            dismissButton = { TextButton(onClick = { searchOpen = false }) { Text("取消") } },
            title = { Text("搜索") },
            text = {
                OutlinedTextField(
                    value = searchQuery,
                    onValueChange = { searchQuery = it },
                    label = { Text("名称、网址、备注或收藏夹") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
            },
        )
    }
}

@Composable
private fun AuthScreen(state: OrbitState) {
    var register by remember { mutableStateOf(false) }
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var captcha by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).padding(24.dp), contentAlignment = Alignment.Center) {
        Surface(shape = MaterialTheme.shapes.large, tonalElevation = 3.dp, modifier = Modifier.fillMaxWidth()) {
            Column(
                Modifier.padding(24.dp).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Text("O", style = MaterialTheme.typography.displaySmall, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                Text(if (register) "注册 Orbit" else "登录你的空间", style = MaterialTheme.typography.headlineMedium)
                Text("收藏、计划、待办、摘录与 Hermes 都在这里。", color = MaterialTheme.colorScheme.onSurfaceVariant)
                OutlinedTextField(
                    value = username,
                    onValueChange = { username = it },
                    label = { Text("用户名") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("密码") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    modifier = Modifier.fillMaxWidth(),
                )
                Button(
                    onClick = { captcha = true },
                    enabled = !state.busy,
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                ) { Text(if (register) "验证并注册" else "验证并登录") }
                TextButton(onClick = { register = !register }) {
                    Text(if (register) "已有账号？返回登录" else "还没有账号？注册一个")
                }
                Text("当前服务器：${state.client.origin}", style = MaterialTheme.typography.labelSmall)
            }
        }
    }

    if (captcha) {
        CaptchaDialog(
            state.client.origin,
            onDismiss = { captcha = false },
            onVerified = {
                captcha = false
                scope.launch { state.authenticate(username, password, register) }
            },
        )
    }
}

private class CaptchaBridge(private val verified: () -> Unit) {
    @JavascriptInterface fun verified() { Handler(Looper.getMainLooper()).post(verified) }
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
private fun CaptchaDialog(origin: String, onDismiss: () -> Unit, onVerified: () -> Unit) {
    val context = LocalContext.current
    val html = remember { context.assets.open("playcaptcha.html").bufferedReader().use { it.readText() } }
    Dialog(onDismissRequest = onDismiss) {
        Surface(shape = MaterialTheme.shapes.large) {
            Column(Modifier.fillMaxWidth().padding(12.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text("完成验证", style = MaterialTheme.typography.titleLarge)
                    TextButton(onClick = onDismiss) { Text("关闭") }
                }
                AndroidView(
                    modifier = Modifier.fillMaxWidth().height(430.dp).semantics { contentDescription = "PlayCaptcha 抓娃娃验证" },
                    factory = { webContext ->
                        WebView(webContext).apply {
                            settings.javaScriptEnabled = true
                            settings.domStorageEnabled = true
                            settings.allowFileAccess = false
                            settings.allowContentAccess = false
                            webViewClient = WebViewClient()
                            addJavascriptInterface(CaptchaBridge(onVerified), "Android")
                            loadDataWithBaseURL("$origin/", html, "text/html", "UTF-8", null)
                        }
                    },
                )
            }
        }
    }
}

@Composable
fun LoadingScreen(label: String) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
            CircularProgressIndicator()
            Text(label)
        }
    }
}

@Composable
fun SectionTitle(title: String, subtitle: String = "", action: (@Composable () -> Unit)? = null) {
    Row(Modifier.fillMaxWidth().padding(bottom = 12.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
            if (subtitle.isNotBlank()) Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (action != null) {
            Spacer(Modifier.width(12.dp))
            action()
        }
    }
}

@Composable
fun EmptyState(text: String) {
    Surface(color = MaterialTheme.colorScheme.surfaceVariant, shape = MaterialTheme.shapes.medium, modifier = Modifier.fillMaxWidth()) {
        Text(text, Modifier.padding(20.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

package cloud.shawnstronger.orbit

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.outlined.AdminPanelSettings
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.Bookmarks
import androidx.compose.material.icons.outlined.CameraRoll
import androidx.compose.material.icons.outlined.ChatBubbleOutline
import androidx.compose.material.icons.outlined.CheckCircleOutline
import androidx.compose.material.icons.outlined.CloudQueue
import androidx.compose.material.icons.outlined.EditNote
import androidx.compose.material.icons.outlined.FormatQuote
import androidx.compose.material.icons.outlined.GridView
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.LocalLibrary
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Today
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.runtime.rememberCoroutineScope
import kotlinx.coroutines.launch

enum class OrbitRoute(
    val label: String,
    val icon: ImageVector,
    val permission: String? = null,
) {
    Dashboard("首页", Icons.Outlined.Home, "content:read"),
    Bookmarks("收藏", Icons.Outlined.Bookmarks, "content:read"),
    Plans("计划", Icons.Outlined.Today, "content:read"),
    Todos("待办", Icons.Outlined.CheckCircleOutline, "content:read"),
    More("更多", Icons.Outlined.GridView),
    Library("共享图书馆", Icons.Outlined.LocalLibrary, "library:read"),
    Writings("写点什么", Icons.Outlined.EditNote, "content:read"),
    FilmDiary("胶片日记", Icons.Outlined.CameraRoll, "content:read"),
    Excerpts("摘录", Icons.Outlined.FormatQuote, "content:read"),
    Netdisk("网盘搜索", Icons.Outlined.CloudQueue, "netdisk:search"),
    Chat("Hermes", Icons.Outlined.ChatBubbleOutline, "hermes:chat"),
    Admin("用户管理", Icons.Outlined.AdminPanelSettings, "users:manage"),
    Hermes("Hermes 管理", Icons.Outlined.AutoAwesome, "agents:manage"),
}

val PrimaryRoutes = listOf(OrbitRoute.Dashboard, OrbitRoute.Bookmarks, OrbitRoute.Plans, OrbitRoute.Todos, OrbitRoute.More)
val MoreRoutes = listOf(
    OrbitRoute.Library,
    OrbitRoute.Writings,
    OrbitRoute.FilmDiary,
    OrbitRoute.Excerpts,
    OrbitRoute.Netdisk,
    OrbitRoute.Chat,
    OrbitRoute.Admin,
    OrbitRoute.Hermes,
)

fun OrbitRoute.bottomDestination(): OrbitRoute = if (this in PrimaryRoutes) this else OrbitRoute.More

fun OrbitRoute.backDestination(): OrbitRoute? = when {
    this in MoreRoutes -> OrbitRoute.More
    this != OrbitRoute.Dashboard -> OrbitRoute.Dashboard
    else -> null
}

fun OrbitRoute.isVisibleTo(user: OrbitUser): Boolean = permission == null || user.can(permission)

fun visiblePrimaryRoutes(user: OrbitUser): List<OrbitRoute> =
    PrimaryRoutes.filter { it.isVisibleTo(user) }

fun visibleMoreRoutes(user: OrbitUser): List<OrbitRoute> =
    MoreRoutes.filter { it.isVisibleTo(user) }

@Composable
@OptIn(ExperimentalMaterial3Api::class)
fun AppShell(
    state: OrbitState,
    route: OrbitRoute,
    onRoute: (OrbitRoute) -> Unit,
    onLogout: () -> Unit,
) {
    val user = requireNotNull(state.user)
    val scope = rememberCoroutineScope()
    val back = route.backDestination()?.takeIf { it.isVisibleTo(user) }

    BackHandler(enabled = back != null) { back?.let(onRoute) }

    LaunchedEffect(route) {
        if (!route.isVisibleTo(user)) {
            onRoute(OrbitRoute.More)
            return@LaunchedEffect
        }
        when (route) {
            OrbitRoute.Library -> state.loadLibrary()
            OrbitRoute.Chat -> state.loadConversations()
            OrbitRoute.Admin -> state.loadAdmin()
            OrbitRoute.Hermes -> state.loadHermesStatus()
            else -> Unit
        }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                navigationIcon = {
                    if (route in MoreRoutes) {
                        IconButton(onClick = { onRoute(OrbitRoute.More) }) {
                            Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = "返回更多")
                        }
                    }
                },
                title = {
                    Text(if (route in PrimaryRoutes) "Orbit" else route.label, style = MaterialTheme.typography.titleLarge)
                },
                actions = {
                    if (route == OrbitRoute.Dashboard) {
                        IconButton(onClick = { scope.launch { state.refreshContent() } }, enabled = !state.busy) {
                            Icon(Icons.Outlined.Refresh, contentDescription = "刷新内容")
                        }
                    }
                },
            )
        },
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                visiblePrimaryRoutes(user).forEach { destination ->
                    NavigationBarItem(
                        selected = route.bottomDestination() == destination,
                        onClick = { onRoute(destination) },
                        icon = { Icon(destination.icon, contentDescription = null) },
                        label = { Text(destination.label) },
                    )
                }
            }
        },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) {
            when (route) {
                OrbitRoute.Dashboard -> DashboardScreen(state, onRoute)
                OrbitRoute.Bookmarks -> BookmarksScreen(state)
                OrbitRoute.Plans -> PlansScreen(state)
                OrbitRoute.Todos -> TodosScreen(state)
                OrbitRoute.More -> MoreScreen(state, onRoute, onLogout)
                OrbitRoute.Library -> LibraryScreen(state)
                OrbitRoute.Writings -> WritingsScreen(state)
                OrbitRoute.FilmDiary -> FilmDiaryScreen(state)
                OrbitRoute.Excerpts -> ExcerptsScreen(state)
                OrbitRoute.Netdisk -> NetdiskScreen(state)
                OrbitRoute.Chat -> HermesChatScreen(state)
                OrbitRoute.Admin -> AdminScreen(state)
                OrbitRoute.Hermes -> HermesScreen(state)
            }
            if (state.busy) {
                Box(
                    Modifier.fillMaxSize().background(MaterialTheme.colorScheme.scrim.copy(alpha = .32f)),
                    contentAlignment = Alignment.Center,
                ) {
                    CircularProgressIndicator(color = MaterialTheme.colorScheme.primaryContainer)
                }
            }
        }
    }
}

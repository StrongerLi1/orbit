package cloud.shawnstronger.orbit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NavigationTest {
    private fun user(vararg permissions: String) = OrbitUser(
        id = "u",
        username = "reader",
        isAdmin = false,
        isBanned = false,
        roles = listOf("user"),
        permissions = permissions.toList(),
        createdAt = "",
        lastLoginAt = "",
    )

    @Test
    fun primaryNavigationKeepsMoreAndFiltersProtectedDestinations() {
        val routes = visiblePrimaryRoutes(user("content:read"))
        assertEquals(listOf(OrbitRoute.Dashboard, OrbitRoute.Bookmarks, OrbitRoute.Plans, OrbitRoute.Todos, OrbitRoute.More), routes)
        assertEquals(listOf(OrbitRoute.More), visiblePrimaryRoutes(user()))
        assertFalse(OrbitRoute.Dashboard.isVisibleTo(user()))
        assertTrue(OrbitRoute.More.isVisibleTo(user()))
    }

    @Test
    fun moreNavigationUsesServerPermissions() {
        val normal = visibleMoreRoutes(user("content:read", "netdisk:search", "hermes:chat"))
        assertEquals(
            listOf(OrbitRoute.Writings, OrbitRoute.FilmDiary, OrbitRoute.Excerpts, OrbitRoute.Netdisk, OrbitRoute.Chat),
            normal,
        )
        assertFalse(OrbitRoute.Admin in normal)

        val libraryReader = visibleMoreRoutes(user("library:read"))
        assertEquals(listOf(OrbitRoute.Library), libraryReader)
        assertFalse(OrbitRoute.Library in visibleMoreRoutes(user("library:upload")))

        val admin = visibleMoreRoutes(user("content:read", "users:manage", "agents:manage"))
        assertTrue(OrbitRoute.Admin in admin)
        assertTrue(OrbitRoute.Hermes in admin)

        assertEquals(emptyList<OrbitRoute>(), visibleMoreRoutes(user()).filter { it != OrbitRoute.More })
    }

    @Test
    fun secondaryRoutesSelectAndReturnToMore() {
        MoreRoutes.forEach { route ->
            assertEquals(OrbitRoute.More, route.bottomDestination())
            assertEquals(OrbitRoute.More, route.backDestination())
        }
        assertEquals(OrbitRoute.Dashboard, OrbitRoute.Bookmarks.backDestination())
        assertEquals(null, OrbitRoute.Dashboard.backDestination())
    }
}

package cloud.shawnstronger.orbit

import android.annotation.SuppressLint
import android.content.Context
import android.location.Geocoder
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Looper
import android.Manifest
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import java.util.Locale
import kotlin.coroutines.resume

suspend fun currentReadableAddress(context: Context): String? = withTimeoutOrNull(15_000) {
    val allowed = listOf(Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.ACCESS_FINE_LOCATION).any {
        ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED
    }
    if (!allowed) return@withTimeoutOrNull null
    val location = currentLocation(context) ?: return@withTimeoutOrNull null
    withContext(Dispatchers.IO) {
        if (!Geocoder.isPresent()) return@withContext null
        @Suppress("DEPRECATION")
        runCatching {
            Geocoder(context, Locale.getDefault())
                .getFromLocation(location.latitude, location.longitude, 1)
                ?.firstOrNull()
                ?.getAddressLine(0)
                ?.trim()
                ?.takeIf(String::isNotBlank)
        }.getOrNull()
    }
}

@SuppressLint("MissingPermission")
private suspend fun currentLocation(context: Context): Location? = withTimeoutOrNull(12_000) {
    suspendCancellableCoroutine { continuation ->
        val manager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        val providers = listOf(LocationManager.NETWORK_PROVIDER, LocationManager.GPS_PROVIDER)
            .filter { provider -> runCatching { manager.isProviderEnabled(provider) }.getOrDefault(false) }
        if (providers.isEmpty()) {
            continuation.resume(null)
            return@suspendCancellableCoroutine
        }

        val recent = providers.mapNotNull { provider -> runCatching { manager.getLastKnownLocation(provider) }.getOrNull() }
            .filter { location -> System.currentTimeMillis() - location.time <= 120_000 }
            .maxByOrNull { location -> location.time }
        if (recent != null) {
            continuation.resume(recent)
            return@suspendCancellableCoroutine
        }

        lateinit var listener: LocationListener
        fun finish(location: Location?) {
            runCatching { manager.removeUpdates(listener) }
            if (continuation.isActive) continuation.resume(location)
        }
        listener = LocationListener { location -> finish(location) }
        continuation.invokeOnCancellation { runCatching { manager.removeUpdates(listener) } }
        var requested = false
        providers.forEach { provider ->
            @Suppress("DEPRECATION")
            runCatching { manager.requestSingleUpdate(provider, listener, Looper.getMainLooper()) }
                .onSuccess { requested = true }
        }
        if (!requested) finish(null)
    }
}

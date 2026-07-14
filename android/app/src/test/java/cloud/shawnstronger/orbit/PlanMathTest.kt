package cloud.shawnstronger.orbit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

class PlanMathTest {
    private fun plan(
        frequency: String = "daily",
        target: Int = 1,
        start: String = "2026-07-01",
        end: String = "",
        completions: Map<String, Int> = emptyMap(),
    ) = Plan("p", "Read", frequency, target, start, end, completions, "09:00", 30, "violet", "")

    @Test fun activeRangeIsInclusive() {
        val value = plan(start = "2026-07-02", end = "2026-07-04")
        assertFalse(PlanMath.isActive(value, LocalDate.parse("2026-07-01")))
        assertTrue(PlanMath.isActive(value, LocalDate.parse("2026-07-02")))
        assertTrue(PlanMath.isActive(value, LocalDate.parse("2026-07-04")))
        assertFalse(PlanMath.isActive(value, LocalDate.parse("2026-07-05")))
    }

    @Test fun weeklyProgressStartsOnMonday() {
        val value = plan(
            frequency = "weekly", target = 3,
            completions = mapOf("2026-07-06" to 1, "2026-07-08" to 2, "2026-07-12" to 1, "2026-07-13" to 7),
        )
        assertEquals(PlanProgress(4, 3), PlanMath.progress(value, LocalDate.parse("2026-07-12")))
        assertEquals(PlanProgress(7, 3), PlanMath.progress(value, LocalDate.parse("2026-07-13")))
    }

    @Test fun monthlyProgressDoesNotCrossBoundary() {
        val value = plan(frequency = "monthly", target = 4, completions = mapOf("2026-06-30" to 3, "2026-07-01" to 2))
        assertEquals(2, PlanMath.progress(value, LocalDate.parse("2026-07-31")).done)
    }

    @Test fun historyCountsSuccessfulPeriodsAndTotals() {
        val value = plan(
            frequency = "weekly", target = 2, start = "2026-07-06",
            completions = mapOf("2026-07-06" to 2, "2026-07-13" to 1),
        )
        assertEquals(PlanHistory(2, 1, 3), PlanMath.history(value, LocalDate.parse("2026-07-19")))
    }

    @Test fun dailyHistoryIncludesZeroCountDays() {
        val value = plan(target = 1, start = "2026-07-01", completions = mapOf("2026-07-01" to 1, "2026-07-03" to 2))
        assertEquals(PlanHistory(3, 2, 3), PlanMath.history(value, LocalDate.parse("2026-07-03")))
        assertEquals(0, PlanMath.executionsForDate(listOf(value), LocalDate.parse("2026-07-02")))
    }

    @Test fun monthlyHistoryHonorsEndDate() {
        val value = plan(
            frequency = "monthly", target = 2, start = "2026-01-20", end = "2026-03-03",
            completions = mapOf("2026-01-21" to 2, "2026-02-01" to 1, "2026-03-01" to 2),
        )
        assertEquals(PlanHistory(3, 2, 5), PlanMath.history(value, LocalDate.parse("2026-07-01")))
    }

    @Test fun removalToZeroProducesNoExecution() {
        val value = plan(completions = emptyMap())
        assertEquals(PlanProgress(0, 1), PlanMath.progress(value, LocalDate.parse("2026-07-01")))
    }
}

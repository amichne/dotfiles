// Shorter retention than Gradle's defaults (30 days downloaded, 7 days created
// and build cache) to bound ~/.gradle growth across many worktrees.
beforeSettings {
    caches {
        downloadedResources.setRemoveUnusedEntriesAfterDays(14)
        createdResources.setRemoveUnusedEntriesAfterDays(4)
        buildCache.setRemoveUnusedEntriesAfterDays(4)
    }
}

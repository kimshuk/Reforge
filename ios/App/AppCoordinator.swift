import Foundation
import Combine

enum AppTab: Hashable {
    case home
    case myNotes
}

enum NotesRoute: Hashable {
    case detail(UUID)
    case trash
}

@MainActor
final class AppCoordinator: ObservableObject {
    @Published var selectedTab: AppTab = .home
    @Published var notesPath: [NotesRoute] = []
    let homeViewModel: HomeViewModel

    private let router: PendingNoteRouter
    private let purgeExpiredTrash: (Date) throws -> Void
    private let now: () -> Date

    init(
        homeViewModel: HomeViewModel,
        router: PendingNoteRouter,
        purgeExpiredTrash: @escaping (Date) throws -> Void,
        now: @escaping () -> Date = Date.init
    ) {
        self.homeViewModel = homeViewModel
        self.router = router
        self.purgeExpiredTrash = purgeExpiredTrash
        self.now = now
    }

    func activate() {
        try? purgeExpiredTrash(now().addingTimeInterval(-30 * 24 * 60 * 60))
        try? router.consumeLatest { noteID in
            openNote(noteID)
        }
    }

    func openNote(_ noteID: UUID) {
        selectedTab = .myNotes
        notesPath = [.detail(noteID)]
    }

    func analyze(_ note: StoredContentNote) async {
        homeViewModel.applySharedNote(note)
        selectedTab = .home
        await homeViewModel.analyze()
    }
}

import Darwin
import Foundation

enum SharedStoreLockError: Error, Equatable {
    case openFailed(Int32)
    case acquireFailed(Int32)
}

final class SharedStoreLock: @unchecked Sendable {
    let fileURL: URL

    init(fileURL: URL) {
        self.fileURL = fileURL
    }

    nonisolated func withLock<T>(_ operation: () throws -> T) throws -> T {
        try FileManager.default.createDirectory(
            at: fileURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let descriptor = Darwin.open(
            fileURL.path,
            O_CREAT | O_RDWR,
            S_IRUSR | S_IWUSR
        )
        guard descriptor >= 0 else {
            throw SharedStoreLockError.openFailed(errno)
        }
        defer { Darwin.close(descriptor) }

        guard flock(descriptor, LOCK_EX) == 0 else {
            throw SharedStoreLockError.acquireFailed(errno)
        }
        defer { flock(descriptor, LOCK_UN) }

        return try operation()
    }
}

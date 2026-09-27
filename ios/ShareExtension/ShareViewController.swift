import Combine
import UIKit

@MainActor
final class ShareViewController: UIViewController {
    private let statusLabel = UILabel()
    private let spinner = UIActivityIndicatorView(style: .medium)
    private var ingestionTask: Task<Void, Never>?
    private var cancellables = Set<AnyCancellable>()

    override func viewDidLoad() {
        super.viewDidLoad()
        configureView()
        ingestionTask = Task { [weak self] in
            await self?.run()
        }
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        ingestionTask?.cancel()
    }

    deinit {
        ingestionTask?.cancel()
    }

    private func configureView() {
        view.backgroundColor = .systemBackground
        statusLabel.numberOfLines = 0
        statusLabel.textAlignment = .center
        statusLabel.translatesAutoresizingMaskIntoConstraints = false
        spinner.translatesAutoresizingMaskIntoConstraints = false
        spinner.startAnimating()
        view.addSubview(statusLabel)
        view.addSubview(spinner)
        NSLayoutConstraint.activate([
            spinner.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            spinner.centerYAnchor.constraint(equalTo: view.centerYAnchor, constant: -20),
            statusLabel.topAnchor.constraint(equalTo: spinner.bottomAnchor, constant: 16),
            statusLabel.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 24),
            statusLabel.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -24),
        ])
    }

    private func run() async {
        guard let context = extensionContext else { return }
        do {
            let input = try await ShareInputLoader().load(
                from: context.inputItems.compactMap { $0 as? NSExtensionItem }
            )
            let container = try SharedModelContainer.makeAppGroupContainer()
            let repository = ContentNoteRepository(
                container: container,
                lock: try SharedModelContainer.appGroupLock()
            )
            guard let baseURL = URL(string: AppConfig.default.backendBaseURL) else {
                throw ShareInputLoaderError.invalidInput
            }
            let coordinator = ShareIngestionCoordinator(
                repository: repository,
                transcriptService: URLSessionYouTubeTranscriptService(baseURL: baseURL)
            )
            let viewModel = ShareExtensionViewModel(
                ingestor: coordinator,
                complete: { [weak context] in
                    context?.completeRequest(returningItems: nil)
                },
                cancel: { [weak context] in
                    context?.cancelRequest(withError: CancellationError())
                }
            )
            bind(viewModel)
            await viewModel.run(input: input)
        } catch {
            context.cancelRequest(withError: error)
        }
    }

    private func bind(_ viewModel: ShareExtensionViewModel) {
        viewModel.$statusText
            .sink { [weak self] text in self?.statusLabel.text = text }
            .store(in: &cancellables)
        viewModel.$isLoading
            .sink { [weak self] isLoading in
                if isLoading {
                    self?.spinner.startAnimating()
                } else {
                    self?.spinner.stopAnimating()
                }
            }
            .store(in: &cancellables)
    }
}

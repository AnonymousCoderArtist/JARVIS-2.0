"""Training data for query type classification with comprehensive augmentation."""

# Base training data - 40 examples per category
TRAINING_DATA = {
    "bug_fix": [
        "fix the bug in main function",
        "there's an error happening in production",
        "this feature is broken",
        "something is wrong with the parser",
        "resolve the issue immediately",
        "debug this code urgently",
        "the test suite is failing",
        "fix the null pointer exception",
        "why is this application crashing",
        "the server keeps crashing",
        "there's a memory leak somewhere",
        "fix the race condition bug",
        "the output format is incorrect",
        "the function returns None unexpectedly",
        "something broke after the update",
        "button click handler not working",
        "api endpoint returns 500 error",
        "user authentication is failing",
        "database save operation not working",
        "connection timeout errors",
        "fix the segmentation fault",
        "resolve the deadlock in worker thread",
        "patch the security vulnerability",
        "the infinite loop never stops",
        "fix the off by one error",
        "correct the logical error",
        "solve the stack overflow issue",
        "the query returns wrong results",
        "fix inconsistent data state",
        "handle the exception properly",
        "repair the broken functionality",
        "patch the payment bug",
        "fix token expiry issue",
        "resolve the null reference",
        "debug the silent failure",
        "the dashboard won't load",
        "fix the broken pagination",
        "correct the calculation error",
        "stop the infinite recursion",
        "fix the memory corruption",
    ],
    "code_review": [
        "review my code for potential bugs",
        "check the implementation thoroughly",
        "analyze the function logic",
        "look at this class design",
        "inspect the module structure",
        "review the recent changes",
        "audit the code quality",
        "what issues does this code have",
        "is this implementation correct",
        "find problems in the algorithm",
        "evaluate this code thoroughly",
        "code review the entire file",
        "check for potential issues",
        "review the control flow",
        "spot potential bugs",
        "examine the algorithm efficiency",
        "assess the code quality metrics",
        "critique the design patterns used",
        "validate the approach taken",
        "verify the implementation",
        "what can be improved here",
        "are there any potential issues",
        "review this pull request",
        "analyze code performance bottlenecks",
        "check error handling coverage",
        "review security considerations",
        "assess the architecture design",
        "evaluate the patterns used",
        "review edge case handling",
        "check for code smells",
        "is this following best practices",
        "review the data flow",
        "analyze dependencies",
        "check for bottlenecks",
        "review error response handling",
        "examine the api design",
        "validate the schema",
        "review the contracts between modules",
        "check type safety",
        "assess maintainability score",
    ],
    "implementation": [
        "implement a new feature request",
        "create a user authentication module",
        "build a rest api from scratch",
        "add a caching layer to system",
        "write a new utility function",
        "develop the login system",
        "add file upload capability",
        "create a database schema",
        "implement the observer pattern",
        "build a cli tool for automation",
        "add email notification service",
        "create a webhook handler",
        "implement rate limiting logic",
        "add search functionality",
        "build an admin dashboard",
        "create a user profile page",
        "implement pagination logic",
        "add user role management",
        "build notification system",
        "create data export feature",
        "implement input validation",
        "add batch processing capability",
        "build import functionality",
        "implement real-time updates",
        "add analytics tracking",
        "create audit logging system",
        "implement password reset flow",
        "add two-factor authentication",
        "build api versioning system",
        "implement webhook retry logic",
        "add request validation middleware",
        "create logging middleware",
        "implement session management",
        "add oauth integration",
        "build recommendation engine",
        "implement message queue processor",
        "add background job processing",
        "create data pipeline",
        "implement search indexing",
        "add autocomplete feature",
    ],
    "refactor": [
        "refactor this code for clarity",
        "restructure the entire project",
        "clean up this messy module",
        "optimize performance bottlenecks",
        "make the code more readable",
        "reduce the complexity score",
        "simplify the nested logic",
        "extract reusable functions",
        "remove duplicate code blocks",
        "improve the overall design",
        "modernize the codebase",
        "reorganize project structure",
        "apply solid design principles",
        "make it more maintainable",
        "reduce coupling between modules",
        "reduce cyclomatic complexity",
        "extract magic numbers to constants",
        "rename unclear variable names",
        "split large functions",
        "consolidate duplicate logic",
        "add proper abstractions",
        "remove dead code paths",
        "apply design patterns appropriately",
        "improve naming conventions",
        "break circular dependencies",
        "extract shared utilities",
        "introduce interface abstractions",
        "decouple components properly",
        "flatten nested conditionals",
        "replace magic numbers with constants",
        "use composition over inheritance",
        "simplify boolean expressions",
        "extract configuration to files",
        "consolidate error handling",
        "improve testability score",
        "reduce function parameters",
        "extract helper methods",
        "inline redundant variables",
        "introduce domain objects",
        "move methods closer to data",
    ],
    "documentation": [
        "add documentation to all functions",
        "write a comprehensive readme",
        "document the api endpoints",
        "explain how this works",
        "add comments to the code",
        "create a user guide",
        "document the function parameters",
        "write usage examples",
        "add docstrings everywhere",
        "create architecture documentation",
        "explain the workflow",
        "document design decisions",
        "write the changelog",
        "create api documentation",
        "add inline code comments",
        "document configuration options",
        "write installation guide",
        "add code examples",
        "document error codes",
        "create troubleshooting guide",
        "write contributing guidelines",
        "document the data model",
        "add migration guide",
        "create quick start guide",
        "document the cli commands",
        "write deployment guide",
        "add security considerations",
        "document testing strategy",
        "create developer documentation",
        "explain caching strategy",
        "document authentication flow",
        "write the complete api reference",
        "add architecture diagrams",
        "document message formats",
        "create operational runbook",
        "document environment variables",
        "write licensing terms",
        "add badges to readme",
        "document webhook events",
        "explain rate limit policies",
    ],
    "testing": [
        "write comprehensive tests",
        "add thorough unit tests",
        "increase test coverage",
        "test all edge cases",
        "add integration tests",
        "write detailed test cases",
        "setup pytest configuration",
        "add proper assertions",
        "test the main function",
        "create test fixtures",
        "add sufficient test coverage",
        "write specification tests",
        "add mock object tests",
        "test happy path and error cases",
        "validate functionality with tests",
        "write end-to-end tests",
        "add regression test suite",
        "create mock objects",
        "setup test database",
        "write smoke test suite",
        "add performance tests",
        "create load test scenarios",
        "write security test cases",
        "add api endpoint tests",
        "test authentication flows",
        "create component test suite",
        "write contract test cases",
        "add mutation testing",
        "test error handling paths",
        "validate with assertions",
        "write snapshot tests",
        "add flaky test detection",
        "create test data factories",
        "write parameterized tests",
        "add benchmark tests",
        "test concurrent execution",
        "write ui integration tests",
        "add browser automation tests",
        "validate form submissions",
        "test file upload handling",
    ],
}


def get_training_data() -> list[tuple[str, str]]:
    """Get training data as list of (text, label) tuples."""
    data = []
    for label, examples in TRAINING_DATA.items():
        for example in examples:
            data.append((example, label))
    return data


def get_label_distribution() -> dict[str, int]:
    """Get the distribution of labels."""
    return {label: len(examples) for label, examples in TRAINING_DATA.items()}


def augment_training_data(data: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Generate augmented data through paraphrasing and variations."""
    import random
    import re

    augmented = []

    # Paraphrase patterns
    prefixes = [
        "", "please ", "could you ", "can you ", "i need to ", "help me ",
        "would you ", "can we ", "should i ", "want to ",
    ]

    suffixes = [
        "", " please", " thanks", " if possible", " for me", " now",
        " immediately", " as soon as possible", " urgently",
    ]

    # Phrase substitutions for augmentation
    substitutions = {
        r"\bimplement\b": ["create", "build", "add", "develop"],
        r"\bfix\b": ["repair", "resolve", "correct", "patch"],
        r"\breview\b": ["check", "analyze", "audit", "examine"],
        r"\bdocument\b": ["describe", "explain", "detail"],
        r"\btest\b": ["validate", "verify", "check"],
        r"\brefactor\b": ["restructure", "improve", "optimize"],
        r"\bcode\b": ["source", "module", "function"],
        r"\berror\b": ["issue", "problem", "bug", "fault"],
    }

    for text, label in data:
        # Original
        augmented.append((text, label))

        # Prefix/suffix variations
        for prefix in prefixes:
            for suffix in suffixes:
                if prefix or suffix:
                    augmented.append((f"{prefix}{text}{suffix}", label))

        # Phrase substitutions
        augmented_text = text
        for pattern, replacements in substitutions.items():
            if re.search(pattern, augmented_text, re.IGNORECASE):
                for replacement in replacements:
                    new_text = re.sub(pattern, replacement, augmented_text, flags=re.IGNORECASE)
                    if new_text != text:
                        augmented.append((new_text, label))

        # Synonym shuffling for verbs
        verb_shuffles = [
            (r"\bwrite\b", "write"),
            (r"\badd\b", "add"),
            (r"\bcreate\b", "create"),
        ]

        # Capitalization variations
        if random.random() > 0.5:
            augmented.append((text.capitalize(), label))

    return augmented


if __name__ == "__main__":
    data = get_training_data()
    print(f"Base samples: {len(data)}")
    augmented = augment_training_data(data)
    print(f"After augmentation: {len(augmented)}")
    print(f"Distribution: {get_label_distribution()}")

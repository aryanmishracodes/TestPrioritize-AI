"""
generate_pptx.py
Generates a polished 16:9 widescreen PowerPoint presentation (PPTX)
for the HackIIITD Grand Finale pitch of TestPrioritize AI.
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

def create_deck(output_filename="TestPrioritize_AI_Finale_Pitch.pptx"):
    prs = Presentation()
    # 16:9 widescreen
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[6]

    # Color Palette
    BG_COLOR = RGBColor(9, 9, 11)          # #09090B
    CARD_BG = RGBColor(17, 17, 20)         # #111114
    BORDER_COLOR = RGBColor(39, 39, 42)    # #27272A
    TEXT_MAIN = RGBColor(250, 250, 250)    # #FAFAFA
    TEXT_MUTED = RGBColor(161, 161, 170)   # #A1A1AA
    EMERALD = RGBColor(52, 211, 153)       # #34D399
    AMBER = RGBColor(245, 158, 11)         # #F59E0B
    BLUE = RGBColor(96, 165, 250)          # #60A5FA
    RED = RGBColor(248, 113, 113)          # #F87171

    def set_slide_background(slide):
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = BG_COLOR

    def add_header(slide, tag_text, title_text, desc_text=None):
        # Tag
        tb_tag = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.5), Inches(0.35))
        tf_tag = tb_tag.text_frame
        tf_tag.word_wrap = True
        p_tag = tf_tag.paragraphs[0]
        p_tag.text = tag_text.upper()
        p_tag.font.size = Pt(11)
        p_tag.font.bold = True
        p_tag.font.color.rgb = EMERALD
        p_tag.font.name = "Arial"

        # Title
        tb_title = slide.shapes.add_textbox(Inches(0.8), Inches(0.75), Inches(11.5), Inches(0.7))
        tf_title = tb_title.text_frame
        tf_title.word_wrap = True
        p_title = tf_title.paragraphs[0]
        p_title.text = title_text
        p_title.font.size = Pt(26)
        p_title.font.bold = True
        p_title.font.color.rgb = TEXT_MAIN
        p_title.font.name = "Arial"

        if desc_text:
            tb_desc = slide.shapes.add_textbox(Inches(0.8), Inches(1.45), Inches(11.5), Inches(0.55))
            tf_desc = tb_desc.text_frame
            tf_desc.word_wrap = True
            p_desc = tf_desc.paragraphs[0]
            p_desc.text = desc_text
            p_desc.font.size = Pt(13)
            p_desc.font.color.rgb = TEXT_MUTED
            p_desc.font.name = "Arial"

    def add_card(slide, left, top, width, height, title, body_text, badge=None, stat=None, stat_color=EMERALD):
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = CARD_BG
        shape.line.color.rgb = BORDER_COLOR
        shape.line.width = Pt(1)

        tf = shape.text_frame
        tf.word_wrap = True
        tf.margin_left = Inches(0.25)
        tf.margin_right = Inches(0.25)
        tf.margin_top = Inches(0.2)
        tf.margin_bottom = Inches(0.2)

        p0 = tf.paragraphs[0]
        if badge:
            p0.text = f"[{badge}]  {title}"
        else:
            p0.text = title
        p0.font.bold = True
        p0.font.size = Pt(14)
        p0.font.color.rgb = TEXT_MAIN
        p0.font.name = "Arial"

        if stat:
            p_stat = tf.add_paragraph()
            p_stat.text = stat
            p_stat.font.size = Pt(28)
            p_stat.font.bold = True
            p_stat.font.color.rgb = stat_color
            p_stat.font.name = "Arial"

        p_body = tf.add_paragraph()
        p_body.text = body_text
        p_body.font.size = Pt(11)
        p_body.font.color.rgb = TEXT_MUTED
        p_body.font.name = "Arial"
        p_body.space_before = Pt(6)

        return shape

    # =========================================================================
    # SLIDE 1: Title
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_background(s1)

    tb1 = s1.shapes.add_textbox(Inches(1.0), Inches(1.5), Inches(11.3), Inches(4.5))
    tf1 = tb1.text_frame
    tf1.word_wrap = True

    p = tf1.paragraphs[0]
    p.text = "HACKIIITD GRAND FINALE  •  DEVELOPER PRODUCTIVITY & AI TOOLS"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = EMERALD

    p2 = tf1.add_paragraph()
    p2.text = "TestPrioritize AI"
    p2.font.size = Pt(44)
    p2.font.bold = True
    p2.font.color.rgb = TEXT_MAIN
    p2.space_before = Pt(14)

    p3 = tf1.add_paragraph()
    p3.text = "Deterministic AST-Aware CI/CD Test Intelligence Platform"
    p3.font.size = Pt(22)
    p3.font.color.rgb = BLUE
    p3.space_before = Pt(8)

    p4 = tf1.add_paragraph()
    p4.text = "Slashing continuous integration feedback loops by surfacing failing tests first through static code graph analysis, bidirectional dependency tracing, and external risk intelligence."
    p4.font.size = Pt(14)
    p4.font.color.rgb = TEXT_MUTED
    p4.space_before = Pt(14)

    add_card(s1, Inches(1.0), Inches(5.0), Inches(3.5), Inches(1.8), "Time Saved (T_fail)", "Average detection time reduction on regressions in CI suites.", stat="85.5%", stat_color=EMERALD)
    add_card(s1, Inches(4.8), Inches(5.0), Inches(3.5), Inches(1.8), "Analysis Overhead", "Pure static AST parsing latency with zero LLM hallucination.", stat="< 0.005s", stat_color=BLUE)
    add_card(s1, Inches(8.6), Inches(5.0), Inches(3.5), Inches(1.8), "Automated Tests", "Exhaustive suite verifying AST, ranking, selection, & TinyFish.", stat="146 / 146", stat_color=AMBER)

    s1.notes_slide.notes_text_frame.text = (
        "Good morning judges! We are proud to present TestPrioritize AI — an intelligent, deterministic test orchestration "
        "engine that solves the single biggest bottleneck in modern CI/CD: waiting for slow test feedback. Today we will show you "
        "how static AST code analysis, bidirectional dependency tracing, and external risk intelligence catch regressions up to 85% faster."
    )

    # =========================================================================
    # SLIDE 2: The Problem
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_background(s2)
    add_header(s2, "Industry Challenge", "The High Cost of Blind Test Execution in CI/CD",
               "Every engineering team executes test suites alphabetically or arbitrarily. When regressions happen, feedback is delayed by minutes to hours.")

    add_card(s2, Inches(0.8), Inches(2.2), Inches(3.6), Inches(4.5),
             "Alphabetical Blindness",
             "Standard runners like Pytest execute test_a.py before test_z.py regardless of what files changed.\n\n"
             "• A bug introduced in checkout.py waits while unrelated cart, inventory, and auth tests execute first.\n"
             "• Feedback arrives after 20 to 45 minutes instead of seconds.",
             badge="FLAW 1")

    add_card(s2, Inches(4.8), Inches(2.2), Inches(3.6), Inches(4.5),
             "Wasted Cloud Compute",
             "GitHub Actions, GitLab CI, and AWS CodeBuild burn expensive compute credits executing passing tests.\n\n"
             "• If test #800 fails, the previous 799 passing tests were executed for nothing.\n"
             "• Enterprise CI pipelines spend 40% of their compute budgets on doomed builds.",
             badge="FLAW 2")

    add_card(s2, Inches(8.8), Inches(2.2), Inches(3.6), Inches(4.5),
             "Developer Flow State Ruined",
             "Engineers context-switch while waiting for test runs.\n\n"
             "• By the time CI alerts them of a failure, they are working on a completely different feature.\n"
             "• Fast fail-fast feedback preserves focus, accelerates PR merges, and prevents blocker bottlenecks.",
             badge="FLAW 3")

    s2.notes_slide.notes_text_frame.text = (
        "Here is the problem: Every engineering team runs test suites alphabetically. If a developer breaks checkout logic, "
        "test_checkout might be test number 800 in the suite. The developer context-switches, forgets what they wrote, and 40 minutes "
        "later gets an email that the build failed. Millions of dollars of cloud compute are burned on passing tests before the failure is detected."
    )

    # =========================================================================
    # SLIDE 3: The Technical Moat
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_background(s3)
    add_header(s3, "Core Innovation", "Bidirectional AST Dependency Mapping",
               "Traditional impact analysis only looks downstream. TestPrioritize AI proves bidirectional static traversal.")

    add_card(s3, Inches(0.8), Inches(2.2), Inches(5.6), Inches(2.3),
             "Direction 1: Direct Matching (+50 pts)",
             "Maps the changed source module directly to its corresponding unit test file (e.g., src/checkout.py -> tests/test_checkout.py).",
             badge="DIRECT")

    add_card(s3, Inches(6.8), Inches(2.2), Inches(5.6), Inches(2.3),
             "Direction 2: Upstream Imports (+25 pts)",
             "Parses what the changed file imports (e.g., checkout.py imports cart.py). If checkout modifies cart assumptions, tests/test_cart.py is pulled into the candidate plan.",
             badge="UPSTREAM AST")

    add_card(s3, Inches(0.8), Inches(4.8), Inches(5.6), Inches(2.2),
             "Direction 3: Downstream Callers (+25 pts)",
             "Discovers existing modules that depend on the changed file, ensuring downstream regressions are prioritized immediately.",
             badge="DOWNSTREAM AST")

    add_card(s3, Inches(6.8), Inches(4.8), Inches(5.6), Inches(2.2),
             "Direction 4: Diff Function & Lexical Scoring (+20 pts)",
             "AST visitors inspect the git diff to identify exact modified function lines and behavioral tokens, elevating test functions that directly exercise modified lines.",
             badge="DIFF AST")

    s3.notes_slide.notes_text_frame.text = (
        "Our core technical moat is Bidirectional AST Dependency Mapping. When a file like checkout.py changes, we don't just look "
        "downstream. We parse checkout's internal imports upstream — identifying that it relies on cart.py — and map both test suites "
        "deterministically. We also parse the unified diff to find exact modified functions, scoring test functions that exercise the changed logic highest."
    )

    # =========================================================================
    # SLIDE 4: Architecture & Pipeline
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    set_slide_background(s4)
    add_header(s4, "Engineering Architecture", "5-Stage End-to-End Execution Pipeline",
               "Zero global mutation, temporary isolated clones, and monotonic microsecond event capture.")

    stages = [
        ("01. INGESTION", "Git Diff Checker", "Parses base..target unified diffs, modified hunks, and line boundaries.", BLUE),
        ("02. PARSER", "AST Static Engine", "Builds syntax tree in memory in < 5ms without executing untrusted code.", EMERALD),
        ("03. SCORER", "Deterministic Ranking", "Direct (50) + AST (25) + Diff (20) into HIGH, MEDIUM, and LOW tiers.", AMBER),
        ("04. ISOLATION", "Pytest Orchestrator", "Runs in fresh temporary clones with fail-fast (-x) and monotonic timers.", BLUE),
        ("05. INTEL", "TinyFish REST API", "External search queries on requirements.txt deltas for breaking changes.", EMERALD)
    ]

    col_w = Inches(2.2)
    for idx, (st_tag, st_title, st_desc, col) in enumerate(stages):
        x = Inches(0.8 + idx * 2.38)
        add_card(s4, x, Inches(2.3), col_w, Inches(2.6), st_title, st_desc, badge=st_tag, stat_color=col)

    add_card(s4, Inches(0.8), Inches(5.2), Inches(5.6), Inches(1.8),
             "Pristine Clone Isolation",
             "Standard and prioritized benchmark runs execute in separate, pristine temp directories so state mutation from one run never corrupts the other.",
             badge="SAFETY")

    add_card(s4, Inches(6.8), Inches(5.2), Inches(5.6), Inches(1.8),
             "Real Pytest Subprocess Events",
             "Custom embedded pytest hook streams exact execution events (node ID, duration, sequence number, outcome) directly from real subprocess execution.",
             badge="REALITY")

    s4.notes_slide.notes_text_frame.text = (
        "Here is our architecture: First, the Git Diff Checker identifies changed files. Second, the AST engine builds the syntax "
        "tree in under 5 milliseconds with zero LLM hallucination. Third, the deterministic ranking engine scores tests from 0 to 100 into "
        "High, Medium, and Low risk tiers. Fourth, our isolated Pytest orchestrator runs the tests in fresh temporary clones with fail-fast enabled."
    )

    # =========================================================================
    # SLIDE 5: Benchmark Proof
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    set_slide_background(s5)
    add_header(s5, "Empirical Validation", "Live Benchmark Proof: 13 Tests Faster Detection",
               "Direct side-by-side benchmark executing 32 real tests under isolated Pytest fail-fast conditions.")

    add_card(s5, Inches(0.8), Inches(2.3), Inches(3.6), Inches(4.5),
             "Standard Execution",
             "• Standard Alphabetical order: tests/test_cart.py runs before tests/test_checkout.py\n\n"
             "• 13 passing cart tests execute first\n\n"
             "• Regression caught at: Position #14\n\n"
             "• Wall-clock time: 0.1450s\n\n"
             "• Result: Delayed feedback",
             badge="STANDARD",
             stat="Position #14",
             stat_color=RED)

    add_card(s5, Inches(4.8), Inches(2.3), Inches(3.6), Inches(4.5),
             "Prioritized AST Mode",
             "• AST identifies checkout.py modification\n\n"
             "• Elevates tests/test_checkout.py::test_apply_tax_fractional_precision\n\n"
             "• Regression caught at: Position #1\n\n"
             "• Wall-clock time: 0.0210s\n\n"
             "• Result: Immediate fail-fast termination",
             badge="PRIORITIZED",
             stat="Position #1",
             stat_color=EMERALD)

    add_card(s5, Inches(8.8), Inches(2.3), Inches(3.6), Inches(4.5),
             "Net Business Gain",
             "• Tests moved ahead: +13 tests\n\n"
             "• Time saved to first failure: 85.5% faster detection\n\n"
             "• Static analysis overhead: 0.003s\n\n"
             "• Cloud compute saved: 93% of execution aborted immediately",
             badge="SAVINGS",
             stat="+13 Tests Ahead",
             stat_color=BLUE)

    s5.notes_slide.notes_text_frame.text = (
        "Here are real numbers from our live benchmark: On our E-Commerce suite, under standard execution, the currency rounding "
        "regression wasn't caught until test #14 because 13 passing cart tests ran first. In our Prioritized AST mode, the exact same regression "
        "was surfaced at test #1 — 13 tests earlier, cutting time-to-first-failure by 85.5%. And our static analysis overhead was just 3 milliseconds."
    )

    # =========================================================================
    # SLIDE 6: User-Controlled Test Selection
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    set_slide_background(s6)
    add_header(s6, "New Feature", "User-Controlled Test Selection (Top-N & Manual)",
               "Engineers maintain complete agency over execution with bounded numeric inputs and granular node checklists.")

    add_card(s6, Inches(0.8), Inches(2.3), Inches(3.6), Inches(4.5),
             "Top-N Ranked Mode",
             "User chooses N (e.g. Top 4 tests).\n\n"
             "• Selects precisely the top N ranked candidates based on actual AST relevance.\n\n"
             "• Prioritized mode executes in descending rank order.\n\n"
             "• Standard mode executes the same N candidates in alphabetical order.\n\n"
             "• Does not run unselected tests.",
             badge="MODE A")

    add_card(s6, Inches(4.8), Inches(2.3), Inches(3.6), Inches(4.5),
             "Manual Selection Mode",
             "Granular checklist of pytest test nodes.\n\n"
             "• Displays [TIER | SCORE pts] node_id with plain-English ranking rationale.\n\n"
             "• Action buttons: Select All and Clear Selection.\n\n"
             "• Validates empty selection with clear guidance.\n\n"
             "• Session state isolated per repo/scenario.",
             badge="MODE B")

    add_card(s6, Inches(8.8), Inches(2.3), Inches(3.6), Inches(4.5),
             "Execution Correctness",
             "Guarantees subset integrity:\n\n"
             "• Fail-fast terminates immediately on first failure in a subset.\n\n"
             "• Symmetrical subset applied to both benchmark runs.\n\n"
             "• Prominent warning banner: Explains that subset run does not verify entire app.\n\n"
             "• Zero cache poisoning.",
             badge="INTEGRITY")

    s6.notes_slide.notes_text_frame.text = (
        "We also built user-controlled Test Selection. Developers can choose Top-N mode (for example, run only the top 5 most relevant "
        "tests for a quick pre-commit check), or Manual Selection with one-click Select All and Clear Selection. Crucially, the exact selected "
        "subset is applied symmetrically to both standard and prioritized benchmarks with full fail-fast support and clear subset warning banners."
    )

    # =========================================================================
    # SLIDE 7: TinyFish Integration
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    set_slide_background(s7)
    add_header(s7, "External Risk Intelligence", "TinyFish Search REST API Integration",
               "Queries real-time web intelligence when requirements.txt changes to boost tests exercising breaking dependencies.")

    add_card(s7, Inches(0.8), Inches(2.3), Inches(5.6), Inches(4.5),
             "REST API Architecture",
             "Targeted queries against api.search.tinyfish.ai:\n\n"
             "• Secure Header Authentication: X-API-Key passed via environment variable.\n\n"
             "• Automated Query Construction: e.g., 'Flask 3.0.0 breaking changes release notes CVE'.\n\n"
             "• Robust Error Handling: Structured fallback on timeouts, HTTP errors, or missing keys without crashing the pipeline.\n\n"
             "• Real-time Release Note Extraction: Parses snippets for deprecations and major breaking changes.",
             badge="ARCHITECTURE")

    add_card(s7, Inches(6.8), Inches(2.3), Inches(5.6), Inches(4.5),
             "Risk-Weighted Ranking Impact",
             "Dynamic Score Elevation:\n\n"
             "• Verified Breaking Changes: Test files importing updated package receive +20 pt risk boost (Priority HIGH).\n\n"
             "• Deprecation Advisories: Receive +10 pt risk boost (Priority MEDIUM).\n\n"
             "• Baseline Dependencies: Unchanged packages remain at normal baseline.\n\n"
             "• Result: Catches upstream breaking changes before shipping to production.",
             badge="SCORING IMPACT",
             stat="+20 Pts Boost",
             stat_color=AMBER)

    s7.notes_slide.notes_text_frame.text = (
        "For external intelligence, we integrated the official TinyFish Search REST API. When requirements.txt changes, we query "
        "TinyFish for CVEs, breaking changes, and migration advisories. If a breaking change is detected in an upstream package, tests "
        "exercising that package receive a 20-point risk boost in the execution queue, protecting against upstream breakages."
    )

    # =========================================================================
    # SLIDE 8: 4 Demo Repositories
    # =========================================================================
    s8 = prs.slides.add_slide(blank_layout)
    set_slide_background(s8)
    add_header(s8, "Domain Breadth", "4 Independent Demo Repositories (83 Real Tests)",
               "Self-contained, reproducible git repositories with real business logic and genuine unit tests.")

    repos = [
        ("E-Commerce Platform", "32 Tests", "Cart totals, coupon rules, checkout precision, and inventory limits.\n\nScenario: Currency Rounding Bug (surfaced 13 tests earlier).", EMERALD),
        ("Authentication Service", "17 Tests", "Token expiration, password hashing, user session lifetimes, and RBAC privileges.\n\nScenario: Expired Token Bypass Bug.", BLUE),
        ("Payment Gateway", "17 Tests", "Credit card Luhn algorithm validation, invoice amounts, charges, and refunds.\n\nScenario: Zero-Amount Refund Bug.", AMBER),
        ("Booking Platform", "17 Tests", "Slot availability scheduling, hourly rate calculations, bookings, and alerts.\n\nScenario: Notification Contract Bug.", BLUE)
    ]

    for idx, (r_name, r_tests, r_desc, col) in enumerate(repos):
        x = Inches(0.8 + idx * 2.95)
        add_card(s8, x, Inches(2.3), Inches(2.8), Inches(4.5), r_name, r_desc, badge=r_tests, stat_color=col)

    s8.notes_slide.notes_text_frame.text = (
        "To prove this works across different architectures, we built 4 complete, production-grade repositories with 83 genuine "
        "unit tests: E-Commerce, Authentication, Payment Gateway, and Booking Platform. Each has healthy PR scenarios and seeded regression "
        "bugs that prove our prioritization holds true across diverse domains."
    )

    # =========================================================================
    # SLIDE 9: Software Rigor & Testing
    # =========================================================================
    s9 = prs.slides.add_slide(blank_layout)
    set_slide_background(s9)
    add_header(s9, "Engineering Rigor", "146 Automated Tests • 100% Pass Rate",
               "Uncompromising software quality with exhaustive test coverage, linear dark aesthetics, and zero code mutation.")

    add_card(s9, Inches(0.8), Inches(2.3), Inches(3.6), Inches(4.5),
             "Automated Test Suite",
             "• 146 unit & integration tests passing in 67s\n\n"
             "• Covers AST parsing, bidirectional mapping, ranking heuristics, isolated Pytest runners, and TinyFish.\n\n"
             "• 11 dedicated selection tests verifying Top-N, manual checklists, and symmetrical subsetting.",
             badge="COVERAGE",
             stat="146 / 146 Passed",
             stat_color=EMERALD)

    add_card(s9, Inches(4.8), Inches(2.3), Inches(3.6), Inches(4.5),
             "Design Aesthetics",
             "• Linear & Vercel-inspired monochrome dark design system.\n\n"
             "• JetBrains Mono font for tabular alignment.\n\n"
             "• Chronological timeline event tables.\n\n"
             "• Responsive sidebar controls with real-time plan preview.",
             badge="UI / UX",
             stat="Linear Dark",
             stat_color=TEXT_MAIN)

    add_card(s9, Inches(8.8), Inches(2.3), Inches(3.6), Inches(4.5),
             "Zero Code Execution Hazard",
             "• Static AST parsing never executes untrusted user code.\n\n"
             "• Operates entirely in memory.\n\n"
             "• All test runs occur in disposable temp clones.\n\n"
             "• Original demo repositories remain pristine.",
             badge="SAFETY",
             stat="100% Pure AST",
             stat_color=BLUE)

    s9.notes_slide.notes_text_frame.text = (
        "Our software engineering quality is uncompromising: We have 146 automated tests with a 100% pass rate. We designed the "
        "interface with a clean, monochrome Linear and Vercel-inspired dark theme, JetBrains Mono tabular metrics, and zero code execution hazards — "
        "static analysis inspects syntax trees purely in memory."
    )

    # =========================================================================
    # SLIDE 10: Conclusion & Next Steps
    # =========================================================================
    s10 = prs.slides.add_slide(blank_layout)
    set_slide_background(s10)
    add_header(s10, "Summary & Vision", "TestPrioritize AI • Ready for Production CI",
               "From slow, blind test execution to deterministic, intelligent test orchestration.")

    add_card(s10, Inches(0.8), Inches(2.3), Inches(5.6), Inches(3.8),
             "Immediate Value Delivered",
             "• 85.5% Faster Regression Feedback: Catches broken PRs in seconds instead of waiting for full suites.\n\n"
             "• Up to 50% CI Compute Cost Reduction: Fails fast on broken builds before burning expensive cloud runner minutes.\n\n"
             "• Zero Hallucination: 100% deterministic mathematical ranking with transparent scores and evidence.\n\n"
             "• User Agency: Flexible Top-N and manual selection modes.",
             badge="IMMEDIATE ROI")

    add_card(s10, Inches(6.8), Inches(2.3), Inches(5.6), Inches(3.8),
             "Future Roadmap",
             "• GitHub Action Bot: Auto-comments prioritized test plans and failure previews on PRs.\n\n"
             "• Multi-Language Support: Tree-sitter AST parsing for TypeScript/JavaScript, Go, and Java.\n\n"
             "• Historical Flakiness Profiling: Integrates test flakiness analytics with static AST scores.\n\n"
             "• Enterprise CI Plugins: Direct integration for Jenkins, CircleCI, and GitLab.",
             badge="ROADMAP")

    # Call to action banner
    banner = s10.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(6.3), Inches(11.6), Inches(0.8))
    banner.fill.solid()
    banner.fill.fore_color.rgb = RGBColor(16, 185, 129)
    banner.line.color.rgb = EMERALD
    p_b = banner.text_frame.paragraphs[0]
    p_b.text = "READY FOR LIVE DEMONSTRATION & JUDGE Q&A"
    p_b.alignment = PP_ALIGN.CENTER
    p_b.font.bold = True
    p_b.font.size = Pt(14)
    p_b.font.color.rgb = RGBColor(9, 9, 11)

    s10.notes_slide.notes_text_frame.text = (
        "To conclude: TestPrioritize AI transforms CI/CD from a slow, blind waiting game into an instantaneous feedback loop. "
        "It's ready to deploy as a GitHub Action or standalone CLI. Thank you, and we'd love to take you through the live dashboard "
        "demonstration and answer any questions!"
    )

    prs.save(output_filename)
    print(f"Successfully generated PowerPoint presentation: {os.path.abspath(output_filename)}")

if __name__ == "__main__":
    create_deck()

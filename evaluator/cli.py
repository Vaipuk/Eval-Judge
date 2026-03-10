"""
Evaluation Pipeline CLI

Command-line interface for running evaluations, comparisons, and managing prompts.

Usage:
    python -m evaluator run --prompt <prompt_id>           # Runs eval + aggregation
    python -m evaluator run --prompt <prompt_id> --no-aggregate  # Skip aggregation
    python -m evaluator compare --run1 <run_id> --run2 <run_id>
    python -m evaluator report --run <run_id>
    python -m evaluator aggregate --run <run_id>           # Manual aggregation
    python -m evaluator prompts list
    python -m evaluator prompts register --id <id> --type <type> --model <model> --file <path>
    python -m evaluator prompts set-status --id <id> --status <status>
"""

import argparse
import sys
from pathlib import Path

from .prompt_registry import (
    list_prompts,
    register_prompt,
    set_status,
    get_prompt_entry,
    delete_prompt,
)
from .run import run_evaluation
from .aggregate import aggregate_run, save_aggregation
from .compare import compare_runs, save_comparison
from .report import (
    generate_report,
    generate_comparison_report,
    save_report,
    save_comparison_report,
)


def cmd_run(args):
    """Run evaluation for a prompt version."""
    result = run_evaluation(
        prompt_version=args.prompt,
        skip_confirmation=args.yes,
        max_inputs=args.max_inputs,
    )

    if not result:
        return 1

    # Run aggregation by default (unless --no-aggregate is specified)
    if not args.no_aggregate:
        run_id = result.get("run_id")
        print(f"\nRunning aggregation for {run_id}...")
        agg = aggregate_run(run_id, run_result=result)
        agg_path = save_aggregation(run_id, agg)
        print(f"Aggregation saved to: {agg_path}")

        # Generate report if requested
        if args.report:
            report = generate_report(run_id, run_result=result, aggregation=agg)
            report_path = save_report(run_id, report)
            print(f"Report saved to: {report_path}")

    return 0


def cmd_aggregate(args):
    """Run aggregation on an existing run."""
    print(f"Aggregating run: {args.run}")

    agg = aggregate_run(args.run, cluster_feedback=not args.no_clustering)
    agg_path = save_aggregation(args.run, agg)

    print(f"\nAggregation complete!")
    print(f"Output: {agg_path}")

    # Print summary
    if "overall" in agg:
        overall = agg["overall"]
        print(f"\nOverall Composite Score:")
        print(f"  Mean:   {overall.get('mean', 'N/A')}")
        print(f"  Median: {overall.get('median', 'N/A')}")
        print(f"  Std:    {overall.get('std', 'N/A')}")

    # Print themes
    themes = agg.get("feedback_themes", [])
    if themes:
        print(f"\nTop Feedback Themes:")
        for i, theme in enumerate(themes[:5], 1):
            print(f"  {i}. {theme.get('name', 'Unknown')} ({theme.get('count', 0)} occurrences)")

    return 0


def cmd_compare(args):
    """Compare two evaluation runs."""
    print(f"Comparing runs:")
    print(f"  Baseline:   {args.run1}")
    print(f"  Comparison: {args.run2}")

    comparison = compare_runs(args.run1, args.run2)

    if "error" in comparison:
        print(f"\nError: {comparison['error']}")
        return 1

    # Save comparison result
    comp_path = save_comparison(args.run1, args.run2, comparison)
    print(f"\nComparison saved to: {comp_path}")

    # Generate and save report
    report = generate_comparison_report(comparison)
    report_path = save_comparison_report(args.run1, args.run2, report)
    print(f"Report saved to: {report_path}")

    # Print summary
    overall = comparison.get("overall", {})
    if overall:
        delta = overall.get("delta", 0)
        classification = overall.get("classification", "NO_CHANGE")

        print(f"\nOverall Result:")
        print(f"  Baseline Mean:   {overall.get('run1_mean', 'N/A')}")
        print(f"  Comparison Mean: {overall.get('run2_mean', 'N/A')}")
        print(f"  Delta:           {'+' if delta >= 0 else ''}{delta:.2f}")
        print(f"  Status:          {classification}")

    improvements = comparison.get("improvements", [])
    regressions = comparison.get("regressions", [])

    if improvements:
        print(f"\nImprovements: {', '.join(improvements)}")
    if regressions:
        print(f"Regressions: {', '.join(regressions)}")

    return 0


def cmd_report(args):
    """Generate report for an evaluation run."""
    print(f"Generating report for: {args.run}")

    report = generate_report(args.run)
    report_path = save_report(args.run, report)

    print(f"Report saved to: {report_path}")

    if args.print:
        print("\n" + "=" * 60)
        print(report)

    return 0


def cmd_prompts_list(args):
    """List registered prompts."""
    prompts = list_prompts(status=args.status)

    if not prompts:
        print("No prompts registered.")
        return 0

    print(f"{'ID':<25} {'Type':<10} {'Model':<15} {'Status':<12} {'Date':<12}")
    print("-" * 80)

    for p in prompts:
        print(
            f"{p.get('id', 'Unknown'):<25} "
            f"{p.get('type', 'Unknown'):<10} "
            f"{p.get('model', 'Unknown'):<15} "
            f"{p.get('status', 'Unknown'):<12} "
            f"{p.get('date_created', 'Unknown'):<12}"
        )

    return 0


def cmd_prompts_register(args):
    """Register a new prompt version."""
    print(f"Registering prompt: {args.id}")

    # Handle file/directory input
    prompt = None
    prompts = None
    prompt_dir = None

    if args.file:
        file_path = Path(args.file)
        if file_path.is_dir():
            # Per-type prompts from directory
            prompt_dir = file_path
        elif file_path.is_file():
            # Single unified prompt
            with open(file_path, "r", encoding="utf-8") as f:
                prompt = f.read().strip()
        else:
            print(f"Error: Path not found: {args.file}")
            return 1

    elif args.prompt:
        prompt = args.prompt

    try:
        entry = register_prompt(
            prompt_id=args.id,
            prompt_type=args.type,
            model=args.model,
            description=args.description or f"Prompt version {args.id}",
            prompt=prompt,
            prompt_dir=prompt_dir,
            status=args.status or "draft",
        )
        print(f"Registered prompt: {entry['id']}")
        print(f"  Type: {entry['type']}")
        print(f"  Model: {entry['model']}")
        print(f"  Status: {entry['status']}")

        if entry['type'] == 'per-type':
            prompts_dict = entry.get('prompts', {})
            print(f"  Video types: {', '.join(prompts_dict.keys())}")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_prompts_set_status(args):
    """Update the status of a prompt."""
    success = set_status(args.id, args.status)

    if success:
        print(f"Updated status of '{args.id}' to '{args.status}'")
        return 0
    else:
        print(f"Error: Prompt '{args.id}' not found")
        return 1


def cmd_prompts_show(args):
    """Show details of a prompt."""
    entry = get_prompt_entry(args.id)

    if not entry:
        print(f"Error: Prompt '{args.id}' not found")
        return 1

    print(f"ID: {entry.get('id')}")
    print(f"Type: {entry.get('type')}")
    print(f"Model: {entry.get('model')}")
    print(f"Status: {entry.get('status')}")
    print(f"Description: {entry.get('description')}")
    print(f"Date Created: {entry.get('date_created')}")

    if entry.get('type') == 'unified':
        prompt = entry.get('prompt', '')
        print(f"\nPrompt ({len(prompt)} chars):")
        print("-" * 40)
        print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
    else:
        prompts = entry.get('prompts', {})
        print(f"\nPrompts ({len(prompts)} video types):")
        for vt, p in prompts.items():
            print(f"  - {vt}: {len(p)} chars")

    return 0


def cmd_prompts_delete(args):
    """Delete a prompt from the registry."""
    if not args.yes:
        confirm = input(f"Delete prompt '{args.id}'? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return 0

    success = delete_prompt(args.id)

    if success:
        print(f"Deleted prompt: {args.id}")
        return 0
    else:
        print(f"Error: Prompt '{args.id}' not found")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Evaluation Pipeline CLI",
        prog="python -m evaluator",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # === run command ===
    run_parser = subparsers.add_parser("run", help="Run evaluation for a prompt")
    run_parser.add_argument("--prompt", "-p", required=True, help="Prompt version ID")
    run_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    run_parser.add_argument("--max-inputs", "-n", type=int, help="Limit number of inputs")
    run_parser.add_argument("--no-aggregate", action="store_true", help="Skip aggregation after run")
    run_parser.add_argument("--report", "-r", action="store_true", help="Generate report after")
    run_parser.set_defaults(func=cmd_run)

    # === aggregate command ===
    agg_parser = subparsers.add_parser("aggregate", help="Aggregate run results")
    agg_parser.add_argument("--run", "-r", required=True, help="Run ID to aggregate")
    agg_parser.add_argument("--no-clustering", action="store_true", help="Skip feedback clustering")
    agg_parser.set_defaults(func=cmd_aggregate)

    # === compare command ===
    comp_parser = subparsers.add_parser("compare", help="Compare two runs")
    comp_parser.add_argument("--run1", required=True, help="Baseline run ID")
    comp_parser.add_argument("--run2", required=True, help="Comparison run ID")
    comp_parser.set_defaults(func=cmd_compare)

    # === report command ===
    report_parser = subparsers.add_parser("report", help="Generate report for a run")
    report_parser.add_argument("--run", "-r", required=True, help="Run ID")
    report_parser.add_argument("--print", action="store_true", help="Print report to stdout")
    report_parser.set_defaults(func=cmd_report)

    # === prompts subcommand ===
    prompts_parser = subparsers.add_parser("prompts", help="Manage prompt versions")
    prompts_subparsers = prompts_parser.add_subparsers(dest="prompts_command")

    # prompts list
    list_parser = prompts_subparsers.add_parser("list", help="List registered prompts")
    list_parser.add_argument("--status", "-s", help="Filter by status")
    list_parser.set_defaults(func=cmd_prompts_list)

    # prompts register
    reg_parser = prompts_subparsers.add_parser("register", help="Register a new prompt")
    reg_parser.add_argument("--id", required=True, help="Unique prompt ID")
    reg_parser.add_argument("--type", required=True, choices=["unified", "per-type"], help="Prompt type")
    reg_parser.add_argument("--model", required=True, help="Generation model (e.g., gpt-4o-mini)")
    reg_parser.add_argument("--file", "-f", help="Prompt file or directory")
    reg_parser.add_argument("--prompt", help="Prompt text (for unified)")
    reg_parser.add_argument("--description", "-d", help="Description")
    reg_parser.add_argument("--status", default="draft", help="Status (draft/baseline/production/deprecated)")
    reg_parser.set_defaults(func=cmd_prompts_register)

    # prompts set-status
    status_parser = prompts_subparsers.add_parser("set-status", help="Update prompt status")
    status_parser.add_argument("--id", required=True, help="Prompt ID")
    status_parser.add_argument("--status", required=True, help="New status")
    status_parser.set_defaults(func=cmd_prompts_set_status)

    # prompts show
    show_parser = prompts_subparsers.add_parser("show", help="Show prompt details")
    show_parser.add_argument("--id", required=True, help="Prompt ID")
    show_parser.set_defaults(func=cmd_prompts_show)

    # prompts delete
    del_parser = prompts_subparsers.add_parser("delete", help="Delete a prompt")
    del_parser.add_argument("--id", required=True, help="Prompt ID")
    del_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    del_parser.set_defaults(func=cmd_prompts_delete)

    # Parse args
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "prompts" and not args.prompts_command:
        prompts_parser.print_help()
        return 1

    # Run command
    if hasattr(args, "func"):
        return args.func(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())

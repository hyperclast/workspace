package cmd

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"text/tabwriter"
	"time"

	"github.com/hyperclast/workspace/cli/internal/api"
	"github.com/spf13/cobra"
)

var (
	pageProjectID string
	pageTitle     string
	pageFile      string
	pageFiletype  string
	pageMeta      bool
	pageSource    string
)

var pageCmd = &cobra.Command{
	Use:   "page",
	Short: "Manage pages",
	Long:  `Commands for managing pages.`,
}

var pageNewCmd = &cobra.Command{
	Use:   "new",
	Short: "Create a new page",
	Long: `Create a new page from stdin or a file.

CSV files are auto-detected and displayed as sortable tables in the UI.

Examples:
  # Pipe command output
  cat build.log | hyperclast page new --project proj_abc --title "Build Log"
  ./run-tests.sh 2>&1 | hyperclast page new --project proj_abc --title "Test Results"

  # CSV files are auto-detected
  cat data.csv | hyperclast page new --title "Data"

  # With default project set
  make build 2>&1 | hyperclast page new --title "Build Log"

  # From file
  hyperclast page new --project proj_abc --title "Config" --file ./config.txt

  # Title defaults to timestamp if not provided
  echo "Quick note" | hyperclast page new --project proj_abc

  # Specify filetype explicitly
  echo "# Markdown" | hyperclast page new --project proj_abc --filetype md

  # Include metadata backmatter
  make build | hyperclast page new --project proj_abc --meta --source "make build"`,
	RunE: runPageNew,
}

func runPageNew(cmd *cobra.Command, args []string) error {
	if !cfg.IsAuthenticated() {
		return fmt.Errorf("not authenticated. Run 'hyperclast auth login' first")
	}

	projectID := pageProjectID
	if projectID == "" {
		projectID = cfg.GetDefaultProject()
	}

	if projectID == "" {
		printError("No project specified.")
		printInfo("  Use --project <id> or set a default: hyperclast project use <id>")
		printInfo("  Run 'hyperclast project list' to see available projects.")
		return fmt.Errorf("no project specified")
	}

	content, err := readContent()
	if err != nil {
		return err
	}

	if pageMeta {
		content = appendMetadata(content)
	}

	title := pageTitle
	if title == "" {
		title = generateDefaultTitle()
	}

	// Auto-detect filetype if not explicitly set
	filetype := pageFiletype
	if !cmd.Flags().Changed("filetype") {
		filetype = detectFiletype(content, "txt")
	}

	client := api.NewClient(cfg.APIURL, cfg.Token)
	page, err := client.CreatePage(projectID, title, content, filetype)
	if err != nil {
		return fmt.Errorf("failed to create page: %w", err)
	}

	if outputFmt == "json" {
		return json.NewEncoder(os.Stdout).Encode(page)
	}

	printSuccess("Created page \"%s\" (%s)", page.Title, page.ExternalID)
	printInfo("  %s/pages/%s/", cfg.APIURL[:len(cfg.APIURL)-4], page.ExternalID)

	return nil
}

var pageAppendCmd = &cobra.Command{
	Use:   "append <page-id>",
	Short: "Append content to an existing page",
	Long: `Append content to the end of an existing page.

Examples:
  echo "New log entry" | hyperclast page append page_xyz789
  cat more-logs.txt | hyperclast page append page_xyz789 --meta --source "tail -f logs"`,
	Args: cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		return runPageUpdate(args[0], "append")
	},
}

var pagePrependCmd = &cobra.Command{
	Use:   "prepend <page-id>",
	Short: "Prepend content to an existing page",
	Long: `Prepend content to the beginning of an existing page.

Examples:
  echo "Header info" | hyperclast page prepend page_xyz789`,
	Args: cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		return runPageUpdate(args[0], "prepend")
	},
}

var pageOverwriteCmd = &cobra.Command{
	Use:   "overwrite <page-id>",
	Short: "Replace all content of an existing page",
	Long: `Replace all content of an existing page.

Examples:
  cat updated-config.txt | hyperclast page overwrite page_xyz789`,
	Args: cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		return runPageUpdate(args[0], "overwrite")
	},
}

func runPageUpdate(pageID string, mode string) error {
	if !cfg.IsAuthenticated() {
		return fmt.Errorf("not authenticated. Run 'hyperclast auth login' first")
	}

	content, err := readContent()
	if err != nil {
		return err
	}

	if pageMeta {
		content = appendMetadata(content)
	}

	client := api.NewClient(cfg.APIURL, cfg.Token)
	page, err := client.UpdatePageContent(pageID, content, mode)
	if err != nil {
		return fmt.Errorf("failed to update page: %w", err)
	}

	if outputFmt == "json" {
		return json.NewEncoder(os.Stdout).Encode(page)
	}

	var verb string
	switch mode {
	case "append":
		verb = "Appended to"
	case "prepend":
		verb = "Prepended to"
	case "overwrite":
		verb = "Overwrote"
	}

	printSuccess("%s page \"%s\" (%s)", verb, page.Title, page.ExternalID)
	return nil
}

func readContent() (string, error) {
	var content string
	if pageFile != "" {
		data, err := os.ReadFile(pageFile)
		if err != nil {
			return "", fmt.Errorf("failed to read file: %w", err)
		}
		content = string(data)
	} else {
		stat, _ := os.Stdin.Stat()
		if (stat.Mode() & os.ModeCharDevice) != 0 {
			printError("No content provided. Pipe content or use --file <path>")
			return "", fmt.Errorf("no content provided")
		}

		data, err := io.ReadAll(os.Stdin)
		if err != nil {
			return "", fmt.Errorf("failed to read stdin: %w", err)
		}
		content = string(data)
	}

	if content == "" {
		printError("No content provided. Pipe content or use --file <path>")
		return "", fmt.Errorf("no content provided")
	}

	return content, nil
}

func appendMetadata(content string) string {
	hostname, _ := os.Hostname()
	cwd, _ := os.Getwd()

	meta := "\n\n---\nCaptured by Hyperclast CLI\n"
	if pageSource != "" {
		meta += fmt.Sprintf("Source: %s\n", pageSource)
	}
	meta += fmt.Sprintf("Time: %s\n", time.Now().UTC().Format("2006-01-02 15:04:05 UTC"))
	if hostname != "" {
		meta += fmt.Sprintf("Host: %s\n", hostname)
	}
	if cwd != "" {
		meta += fmt.Sprintf("Directory: %s\n", cwd)
	}
	meta += "---"

	return content + meta
}

var pageListProjectID string

var pageListCmd = &cobra.Command{
	Use:   "list",
	Short: "List pages",
	RunE: func(cmd *cobra.Command, args []string) error {
		if !cfg.IsAuthenticated() {
			return fmt.Errorf("not authenticated. Run 'hyperclast auth login' first")
		}

		projectID := pageListProjectID
		if projectID == "" {
			projectID = cfg.GetDefaultProject()
		}

		client := api.NewClient(cfg.APIURL, cfg.Token)
		pages, err := client.ListPages(projectID)
		if err != nil {
			return err
		}

		if outputFmt == "json" {
			return json.NewEncoder(os.Stdout).Encode(pages)
		}

		if len(pages) == 0 {
			printInfo("No pages found")
			return nil
		}

		w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
		fmt.Fprintln(w, "ID\tTITLE\tUPDATED")
		for _, page := range pages {
			updated := page.Updated
			if updated == "" {
				updated = page.Modified
			}
			if t, err := time.Parse(time.RFC3339, updated); err == nil {
				updated = t.Format("Jan 2, 2006 3:04 PM")
			}
			fmt.Fprintf(w, "%s\t%s\t%s\n", page.ExternalID, page.Title, updated)
		}
		w.Flush()

		return nil
	},
}

var pageGetCmd = &cobra.Command{
	Use:   "get <page-id>",
	Short: "Get page content",
	Long:  `Get the content of a page and output it to stdout.`,
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if !cfg.IsAuthenticated() {
			return fmt.Errorf("not authenticated. Run 'hyperclast auth login' first")
		}

		pageID := args[0]

		client := api.NewClient(cfg.APIURL, cfg.Token)
		page, err := client.GetPage(pageID)
		if err != nil {
			return fmt.Errorf("failed to get page: %w", err)
		}

		if outputFmt == "json" {
			return json.NewEncoder(os.Stdout).Encode(page)
		}

		if page.Details != nil && page.Details.Content != "" {
			fmt.Print(page.Details.Content)
		}

		return nil
	},
}

func generateDefaultTitle() string {
	return time.Now().Format("2006-01-02 3h04pm")
}

// detectFiletype examines the first 10 lines of content to detect CSV format.
// Returns "csv" if content appears to be CSV, otherwise returns defaultType.
func detectFiletype(content string, defaultType string) string {
	if content == "" {
		return defaultType
	}

	// Extract first 10 lines (or fewer if content is shorter)
	lines := make([]string, 0, 10)
	start := 0
	for i := 0; i < len(content) && len(lines) < 10; i++ {
		if content[i] == '\n' {
			line := content[start:i]
			if len(line) > 0 && line[len(line)-1] == '\r' {
				line = line[:len(line)-1]
			}
			lines = append(lines, line)
			start = i + 1
		}
	}
	// Add last line if no trailing newline
	if start < len(content) && len(lines) < 10 {
		lines = append(lines, content[start:])
	}

	if len(lines) == 0 {
		return defaultType
	}

	// Check if lines consistently have delimiters
	csvLines := 0
	for _, line := range lines {
		if line == "" {
			continue
		}
		commas := 0
		tabs := 0
		for _, c := range line {
			if c == ',' {
				commas++
			} else if c == '\t' {
				tabs++
			}
		}
		if commas >= 2 || tabs >= 2 {
			csvLines++
		}
	}

	// Consider CSV if majority of non-empty lines look like CSV
	if csvLines >= 1 && csvLines >= len(lines)/2 {
		return "csv"
	}

	return defaultType
}

func init() {
	rootCmd.AddCommand(pageCmd)
	pageCmd.AddCommand(pageNewCmd)
	pageCmd.AddCommand(pageAppendCmd)
	pageCmd.AddCommand(pagePrependCmd)
	pageCmd.AddCommand(pageOverwriteCmd)
	pageCmd.AddCommand(pageListCmd)
	pageCmd.AddCommand(pageGetCmd)

	pageNewCmd.Flags().StringVar(&pageProjectID, "project", "", "project ID")
	pageNewCmd.Flags().StringVar(&pageTitle, "title", "", "page title (defaults to timestamp)")
	pageNewCmd.Flags().StringVar(&pageFile, "file", "", "read content from file instead of stdin")
	pageNewCmd.Flags().StringVar(&pageFiletype, "filetype", "txt", "file type: txt, md, csv")
	pageNewCmd.Flags().BoolVar(&pageMeta, "meta", false, "append metadata backmatter to content")
	pageNewCmd.Flags().StringVar(&pageSource, "source", "", "source description for metadata")

	pageAppendCmd.Flags().StringVar(&pageFile, "file", "", "read content from file instead of stdin")
	pageAppendCmd.Flags().BoolVar(&pageMeta, "meta", false, "append metadata backmatter to content")
	pageAppendCmd.Flags().StringVar(&pageSource, "source", "", "source description for metadata")

	pagePrependCmd.Flags().StringVar(&pageFile, "file", "", "read content from file instead of stdin")
	pagePrependCmd.Flags().BoolVar(&pageMeta, "meta", false, "append metadata backmatter to content")
	pagePrependCmd.Flags().StringVar(&pageSource, "source", "", "source description for metadata")

	pageOverwriteCmd.Flags().StringVar(&pageFile, "file", "", "read content from file instead of stdin")
	pageOverwriteCmd.Flags().BoolVar(&pageMeta, "meta", false, "append metadata backmatter to content")
	pageOverwriteCmd.Flags().StringVar(&pageSource, "source", "", "source description for metadata")

	pageListCmd.Flags().StringVar(&pageListProjectID, "project", "", "filter by project ID")
}

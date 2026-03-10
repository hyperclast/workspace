package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"text/tabwriter"

	"github.com/hyperclast/workspace/cli/internal/api"
	"github.com/spf13/cobra"
)

var (
	projectOrgID     string
	projectNewOrgID  string
	projectNewDesc   string
	projectNewSetUse bool
)

var projectCmd = &cobra.Command{
	Use:   "project",
	Short: "Manage projects",
	Long:  `Commands for managing projects.`,
}

var projectListCmd = &cobra.Command{
	Use:   "list",
	Short: "List projects",
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := requireAuth(); err != nil {
			return err
		}

		orgID := projectOrgID
		if orgID == "" {
			orgID = cfg.GetDefaultOrg()
		}

		client := api.NewClient(cfg.APIURL, cfg.Token)
		projects, err := client.ListProjects(orgID)
		if err != nil {
			return err
		}

		if outputFmt == "json" {
			return json.NewEncoder(os.Stdout).Encode(projects)
		}

		if len(projects) == 0 {
			printInfo("No projects found")
			return nil
		}

		w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
		_, _ = fmt.Fprintln(w, "ID\tNAME\tORG")
		for _, project := range projects {
			defaultMark := ""
			if project.ExternalID == cfg.GetDefaultProject() {
				defaultMark = " (default)"
			}
			_, _ = fmt.Fprintf(w, "%s\t%s%s\t%s\n", project.ExternalID, project.Name, defaultMark, project.Org.Name)
		}
		_ = w.Flush()

		return nil
	},
}

var projectNewCmd = &cobra.Command{
	Use:   "new <name>",
	Short: "Create a new project",
	Long: `Create a new project in an organization.

Examples:
  # Create in default org
  hyperclast project new "Build Logs"

  # Create in a specific org
  hyperclast project new "Build Logs" --org org_abc123

  # Create with description
  hyperclast project new "Build Logs" --description "CI/CD pipeline output"

  # Create and set as default project
  hyperclast project new "Build Logs" --use`,
	Args: cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := requireAuth(); err != nil {
			return err
		}

		name := args[0]

		if strings.TrimSpace(name) == "" {
			return fmt.Errorf("project name cannot be empty")
		}
		if len(name) > 255 {
			return fmt.Errorf("project name too long (max 255 characters)")
		}

		orgID := projectNewOrgID
		if orgID == "" {
			orgID = cfg.GetDefaultOrg()
		}

		if orgID == "" {
			printError("No organization specified.")
			printInfo("  Use --org <id> or set a default: hyperclast org use <id>")
			printInfo("  Run 'hyperclast org list' to see available organizations.")
			cmd.SilenceErrors = true
			return fmt.Errorf("no organization specified")
		}

		client := api.NewClient(cfg.APIURL, cfg.Token)
		project, err := client.CreateProject(orgID, name, projectNewDesc)
		if err != nil {
			return fmt.Errorf("failed to create project: %w", err)
		}

		if projectNewSetUse {
			cfg.SetDefaultProject(project.ExternalID)
			if err := cfg.Save(); err != nil {
				return fmt.Errorf("failed to save config: %w", err)
			}
		}

		if outputFmt == "json" {
			return json.NewEncoder(os.Stdout).Encode(project)
		}

		printSuccess("Created project \"%s\" (%s)", project.Name, project.ExternalID)
		if projectNewSetUse {
			printInfo("  Set as default project")
		}

		return nil
	},
}

var projectCurrentCmd = &cobra.Command{
	Use:   "current",
	Short: "Show current default project",
	RunE: func(cmd *cobra.Command, args []string) error {
		defaultProject := cfg.GetDefaultProject()

		if outputFmt == "json" {
			return json.NewEncoder(os.Stdout).Encode(map[string]string{
				"project_id": defaultProject,
			})
		}

		if defaultProject == "" {
			printInfo("No default project set")
			printInfo("Run 'hyperclast project use <id>' to set one")
			return nil
		}

		if cfg.IsAuthenticated() {
			client := api.NewClient(cfg.APIURL, cfg.Token)
			project, err := client.GetProject(defaultProject)
			if err == nil {
				printInfo("Default project: %s (%s)", project.Name, project.ExternalID)
				return nil
			}
		}

		printInfo("Default project: %s", defaultProject)
		return nil
	},
}

var projectUseCmd = &cobra.Command{
	Use:   "use <id>",
	Short: "Set default project",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		projectID := args[0]

		if cfg.IsAuthenticated() {
			client := api.NewClient(cfg.APIURL, cfg.Token)
			project, err := client.GetProject(projectID)
			if err != nil {
				return fmt.Errorf("project '%s' not found. Run 'hyperclast project list' to see available projects", projectID)
			}

			cfg.SetDefaultProject(projectID)
			if err := cfg.Save(); err != nil {
				return fmt.Errorf("failed to save config: %w", err)
			}

			printSuccess("Default project set to \"%s\" (%s)", project.Name, projectID)
			return nil
		}

		cfg.SetDefaultProject(projectID)
		if err := cfg.Save(); err != nil {
			return fmt.Errorf("failed to save config: %w", err)
		}

		printSuccess("Default project set to %s", projectID)
		return nil
	},
}

func init() {
	rootCmd.AddCommand(projectCmd)
	projectCmd.AddCommand(projectNewCmd)
	projectCmd.AddCommand(projectListCmd)
	projectCmd.AddCommand(projectCurrentCmd)
	projectCmd.AddCommand(projectUseCmd)

	projectNewCmd.Flags().StringVar(&projectNewOrgID, "org", "", "organization ID (uses default if not specified)")
	projectNewCmd.Flags().StringVar(&projectNewDesc, "description", "", "project description")
	projectNewCmd.Flags().BoolVar(&projectNewSetUse, "use", false, "set as default project after creation")

	projectListCmd.Flags().StringVar(&projectOrgID, "org", "", "filter by organization ID")
}

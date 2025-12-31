package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"text/tabwriter"

	"github.com/hyperclast/workspace/cli/internal/api"
	"github.com/spf13/cobra"
)

var projectOrgID string

var projectCmd = &cobra.Command{
	Use:   "project",
	Short: "Manage projects",
	Long:  `Commands for managing projects.`,
}

var projectListCmd = &cobra.Command{
	Use:   "list",
	Short: "List projects",
	RunE: func(cmd *cobra.Command, args []string) error {
		if !cfg.IsAuthenticated() {
			return fmt.Errorf("not authenticated. Run 'hyperclast auth login' first")
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
		fmt.Fprintln(w, "ID\tNAME\tORG")
		for _, project := range projects {
			defaultMark := ""
			if project.ExternalID == cfg.GetDefaultProject() {
				defaultMark = " (default)"
			}
			fmt.Fprintf(w, "%s\t%s%s\t%s\n", project.ExternalID, project.Name, defaultMark, project.Org.Name)
		}
		w.Flush()

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
	projectCmd.AddCommand(projectListCmd)
	projectCmd.AddCommand(projectCurrentCmd)
	projectCmd.AddCommand(projectUseCmd)

	projectListCmd.Flags().StringVar(&projectOrgID, "org", "", "filter by organization ID")
}

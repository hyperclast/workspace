package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"text/tabwriter"

	"github.com/hyperclast/workspace/cli/internal/api"
	"github.com/spf13/cobra"
)

var orgCmd = &cobra.Command{
	Use:   "org",
	Short: "Manage organizations",
	Long:  `Commands for managing organizations.`,
}

var orgListCmd = &cobra.Command{
	Use:   "list",
	Short: "List organizations you belong to",
	RunE: func(cmd *cobra.Command, args []string) error {
		if !cfg.IsAuthenticated() {
			return fmt.Errorf("not authenticated. Run 'hyperclast auth login' first")
		}

		client := api.NewClient(cfg.APIURL, cfg.Token)
		orgs, err := client.ListOrgs()
		if err != nil {
			return err
		}

		if outputFmt == "json" {
			return json.NewEncoder(os.Stdout).Encode(orgs)
		}

		if len(orgs) == 0 {
			printInfo("No organizations found")
			return nil
		}

		w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
		fmt.Fprintln(w, "ID\tNAME\tDOMAIN")
		for _, org := range orgs {
			defaultMark := ""
			if org.ExternalID == cfg.GetDefaultOrg() {
				defaultMark = " (default)"
			}
			fmt.Fprintf(w, "%s\t%s%s\t%s\n", org.ExternalID, org.Name, defaultMark, org.Domain)
		}
		w.Flush()

		return nil
	},
}

var orgCurrentCmd = &cobra.Command{
	Use:   "current",
	Short: "Show current default organization",
	RunE: func(cmd *cobra.Command, args []string) error {
		defaultOrg := cfg.GetDefaultOrg()

		if outputFmt == "json" {
			return json.NewEncoder(os.Stdout).Encode(map[string]string{
				"org_id": defaultOrg,
			})
		}

		if defaultOrg == "" {
			printInfo("No default organization set")
			printInfo("Run 'hyperclast org use <id>' to set one")
			return nil
		}

		if cfg.IsAuthenticated() {
			client := api.NewClient(cfg.APIURL, cfg.Token)
			orgs, err := client.ListOrgs()
			if err == nil {
				for _, org := range orgs {
					if org.ExternalID == defaultOrg {
						printInfo("Default organization: %s (%s)", org.Name, org.ExternalID)
						return nil
					}
				}
			}
		}

		printInfo("Default organization: %s", defaultOrg)
		return nil
	},
}

var orgUseCmd = &cobra.Command{
	Use:   "use <id>",
	Short: "Set default organization",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		orgID := args[0]

		if cfg.IsAuthenticated() {
			client := api.NewClient(cfg.APIURL, cfg.Token)
			orgs, err := client.ListOrgs()
			if err != nil {
				return err
			}

			found := false
			var orgName string
			for _, org := range orgs {
				if org.ExternalID == orgID {
					found = true
					orgName = org.Name
					break
				}
			}

			if !found {
				return fmt.Errorf("organization '%s' not found. Run 'hyperclast org list' to see available organizations", orgID)
			}

			cfg.SetDefaultOrg(orgID)
			if err := cfg.Save(); err != nil {
				return fmt.Errorf("failed to save config: %w", err)
			}

			printSuccess("Default organization set to \"%s\" (%s)", orgName, orgID)
			return nil
		}

		cfg.SetDefaultOrg(orgID)
		if err := cfg.Save(); err != nil {
			return fmt.Errorf("failed to save config: %w", err)
		}

		printSuccess("Default organization set to %s", orgID)
		return nil
	},
}

func init() {
	rootCmd.AddCommand(orgCmd)
	orgCmd.AddCommand(orgListCmd)
	orgCmd.AddCommand(orgCurrentCmd)
	orgCmd.AddCommand(orgUseCmd)
}

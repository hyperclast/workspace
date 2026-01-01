package cmd

import (
	"testing"
)

// TestDetectFiletype tests the CSV auto-detection logic
func TestDetectFiletype(t *testing.T) {
	tests := []struct {
		name        string
		content     string
		defaultType string
		expected    string
	}{
		// CSV detection - comma delimited
		{
			name:        "simple CSV with commas",
			content:     "name,age,city\nAlice,30,NYC\nBob,25,LA",
			defaultType: "txt",
			expected:    "csv",
		},
		{
			name:        "CSV header only",
			content:     "col1,col2,col3",
			defaultType: "txt",
			expected:    "csv",
		},
		{
			name:        "CSV with quoted fields",
			content:     `"Company","Revenue","Notes"\n"Acme, Inc","$1,000","Good"`,
			defaultType: "txt",
			expected:    "csv",
		},

		// CSV detection - tab delimited
		{
			name:        "simple TSV with tabs",
			content:     "name\tage\tcity\nAlice\t30\tNYC",
			defaultType: "txt",
			expected:    "csv",
		},
		{
			name:        "TSV header only",
			content:     "col1\tcol2\tcol3",
			defaultType: "txt",
			expected:    "csv",
		},

		// Non-CSV content
		{
			name:        "plain text no delimiters",
			content:     "Hello world this is plain text",
			defaultType: "txt",
			expected:    "txt",
		},
		{
			name:        "single column content",
			content:     "line1\nline2\nline3",
			defaultType: "txt",
			expected:    "txt",
		},
		{
			name:        "markdown content",
			content:     "# Heading\n\nSome text here.\n\n- Item 1\n- Item 2",
			defaultType: "md",
			expected:    "md",
		},
		{
			name:        "code content",
			content:     "func main() {\n\tfmt.Println(\"hello\")\n}",
			defaultType: "txt",
			expected:    "txt",
		},
		{
			name:        "log content",
			content:     "[INFO] Starting server\n[ERROR] Failed to connect\n[INFO] Retrying",
			defaultType: "txt",
			expected:    "txt",
		},

		// Edge cases
		{
			name:        "empty content",
			content:     "",
			defaultType: "txt",
			expected:    "txt",
		},
		{
			name:        "whitespace only",
			content:     "   \n   ",
			defaultType: "txt",
			expected:    "txt",
		},
		{
			name:        "single comma not enough (2 cols, needs 3+)",
			content:     "a,b",
			defaultType: "txt",
			expected:    "txt",
		},
		{
			name:        "two commas enough (3 cols)",
			content:     "a,b,c",
			defaultType: "txt",
			expected:    "csv",
		},
		{
			name:        "CRLF line endings",
			content:     "a,b,c\r\n1,2,3\r\n4,5,6",
			defaultType: "txt",
			expected:    "csv",
		},

		// Multi-line validation
		{
			name:        "majority of lines look like CSV",
			content:     "a,b,c\n1,2,3\n4,5,6\n7,8,9",
			defaultType: "txt",
			expected:    "csv",
		},
		{
			name:        "mixed content mostly not CSV",
			content:     "Hello world\nsome text\na,b,c\nmore text\neven more",
			defaultType: "txt",
			expected:    "txt",
		},

		// Real-world examples
		{
			name: "real CSV export",
			content: `company,primary_url,sectors,camp_class
Dots,http://weplaydots.com,Gaming,Playable Media
Roxy,http://www.roxydevice.com,"Hardware,Voice",Audio
Alpine.ai,https://alpine.ai,Bots,Audio`,
			defaultType: "txt",
			expected:    "csv",
		},
		{
			name: "build log output",
			content: `==> Building project...
[1/5] Compiling main.go
[2/5] Compiling utils.go
[3/5] Linking
Build complete in 2.3s`,
			defaultType: "txt",
			expected:    "txt",
		},
		{
			name: "test output",
			content: `=== RUN   TestSomething
--- PASS: TestSomething (0.00s)
=== RUN   TestAnother
--- FAIL: TestAnother (0.01s)
FAIL`,
			defaultType: "txt",
			expected:    "txt",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := detectFiletype(tt.content, tt.defaultType)
			if result != tt.expected {
				t.Errorf("detectFiletype() = %q, want %q", result, tt.expected)
			}
		})
	}
}

// TestDetectFiletypeLargeContent tests detection with large content
func TestDetectFiletypeLargeContent(t *testing.T) {
	// Generate large CSV content (more than 10 lines)
	var content string
	content = "col1,col2,col3\n"
	for i := 0; i < 100; i++ {
		content += "a,b,c\n"
	}

	result := detectFiletype(content, "txt")
	if result != "csv" {
		t.Errorf("Large CSV should be detected as csv, got %q", result)
	}
}

// TestDetectFiletypeOnlyScansFirstLines tests that we only scan first 10 lines
func TestDetectFiletypeOnlyScansFirstLines(t *testing.T) {
	// First 10 lines are CSV, rest is not (but we only check first 10)
	var content string
	for i := 0; i < 10; i++ {
		content += "a,b,c\n"
	}
	for i := 0; i < 100; i++ {
		content += "plain text line\n"
	}

	result := detectFiletype(content, "txt")
	if result != "csv" {
		t.Errorf("Should detect CSV based on first 10 lines, got %q", result)
	}
}

// TestDetectFiletypePreservesExplicitType tests that explicit type should be used
// (this is tested in integration, but documenting the expected behavior)
func TestDetectFiletypeDefaultTypePassthrough(t *testing.T) {
	// When content doesn't look like CSV, should return default
	result := detectFiletype("plain text", "md")
	if result != "md" {
		t.Errorf("Should return default type 'md' for non-CSV, got %q", result)
	}
}

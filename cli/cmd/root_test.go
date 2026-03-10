package cmd

import (
	"testing"

	"github.com/hyperclast/workspace/cli/internal/config"
)

func TestBaseURL(t *testing.T) {
	tests := []struct {
		name   string
		apiURL string
		want   string
	}{
		{
			name:   "strips /api",
			apiURL: "https://hyperclast.com/api",
			want:   "https://hyperclast.com",
		},
		{
			name:   "strips /api/v1",
			apiURL: "https://hyperclast.com/api/v1",
			want:   "https://hyperclast.com",
		},
		{
			name:   "strips /api with trailing slash",
			apiURL: "https://hyperclast.com/api/",
			want:   "https://hyperclast.com",
		},
		{
			name:   "strips /api/v1 with trailing slash",
			apiURL: "https://hyperclast.com/api/v1/",
			want:   "https://hyperclast.com",
		},
		{
			name:   "localhost with port and /api",
			apiURL: "http://localhost:9800/api",
			want:   "http://localhost:9800",
		},
		{
			name:   "localhost with port and /api/v1",
			apiURL: "http://localhost:9800/api/v1",
			want:   "http://localhost:9800",
		},
		{
			name:   "no /api suffix left unchanged",
			apiURL: "https://hyperclast.com",
			want:   "https://hyperclast.com",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg = &config.Config{APIURL: tt.apiURL}
			got := baseURL()
			if got != tt.want {
				t.Errorf("baseURL() = %q, want %q", got, tt.want)
			}
		})
	}
}

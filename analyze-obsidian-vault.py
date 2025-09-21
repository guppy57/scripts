# Install dependencies: pip install tiktoken matplotlib numpy
import os
import csv

try:
    import tiktoken
    encoding = tiktoken.get_encoding("cl100k_base")
    TIKTOKEN_AVAILABLE = True
except ImportError:
    print("Warning: tiktoken not installed. Install with: pip install tiktoken")
    print("Token metrics will be estimated (characters / 4) instead of accurate counts.")
    TIKTOKEN_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    print("Warning: matplotlib/numpy not installed. Install with: pip install matplotlib numpy")
    print("Visualization will be skipped.")
    MATPLOTLIB_AVAILABLE = False

VAULT_DIRECTORY = "/Users/guppy57/GuppyBrain/Zettelkasten"

def export_outliers_to_csv(file_data, token_95th, char_95th):
    # Create output directory
    output_dir = "./out/vault-analysis"
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create output directory '{output_dir}': {e}")
        return
    
    # Identify outliers (files above 95th percentile in either tokens or characters)
    outliers = []
    for file_path, token_count, char_count in file_data:
        if token_count > token_95th or char_count > char_95th:
            # Make path relative to vault directory for cleaner output
            relative_path = os.path.relpath(file_path, VAULT_DIRECTORY)
            outliers.append((relative_path, token_count, char_count))
    
    # Sort alphabetically by file path
    outliers.sort(key=lambda x: x[0])
    
    # Write CSV file
    csv_path = os.path.join(output_dir, "outliers.csv")
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow(['path', 'tokens', 'characters'])
            # Write outlier data
            for relative_path, token_count, char_count in outliers:
                writer.writerow([relative_path, token_count, char_count])
        
        print(f"\nOUTLIER EXPORT:")
        print("-" * 55)
        print(f"Exported {len(outliers)} outlier documents to: {csv_path}")
        if outliers:
            print(f"Sample outliers:")
            for i, (path, tokens, chars) in enumerate(outliers[:3]):
                print(f"  {path} ({tokens:,} tokens, {chars:,} characters)")
            if len(outliers) > 3:
                print(f"  ... and {len(outliers) - 3} more")
        
    except Exception as e:
        print(f"Warning: Could not write CSV file '{csv_path}': {e}")

def create_token_distribution_chart(token_counts, character_counts):
    if not MATPLOTLIB_AVAILABLE:
        return
    
    if not token_counts:
        return
    
    # Calculate outlier thresholds and focused ranges
    token_95th = np.percentile(token_counts, 95)
    char_95th = np.percentile(character_counts, 95)
    token_99th = np.percentile(token_counts, 99)
    char_99th = np.percentile(character_counts, 99)
    
    # Filter data for focused view (95th percentile)
    token_focused = [t for t in token_counts if t <= token_95th]
    char_focused = [c for c in character_counts if c <= char_95th]
    
    # Count outliers
    token_outliers = len([t for t in token_counts if t > token_95th])
    char_outliers = len([c for c in character_counts if c > char_95th])
    
    # Create 2x2 subplot layout
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Obsidian Vault Content Distribution Analysis', fontsize=16, fontweight='bold')
    
    # Calculate adaptive bins for focused data
    token_bins = max(20, min(50, len(token_focused) // 10))
    char_bins = max(20, min(50, len(char_focused) // 10))
    
    # Top-left: Token focused distribution (95th percentile)
    ax1.hist(token_focused, bins=token_bins, alpha=0.7, color='lightsteelblue', edgecolor='black')
    ax1.set_title(f'Token Distribution - Focused View (95% of data)\n{len(token_focused)} docs, {token_outliers} outliers excluded')
    ax1.set_xlabel('Number of Tokens per Document')
    ax1.set_ylabel('Number of Documents')
    ax1.grid(True, alpha=0.3)
    ax1.axvline(np.mean(token_focused), color='red', linestyle='dashed', linewidth=2, label=f'Focused Mean: {np.mean(token_focused):.0f}')
    ax1.axvline(np.median(token_focused), color='orange', linestyle='dashed', linewidth=2, label=f'Focused Median: {np.median(token_focused):.0f}')
    ax1.axvline(token_95th, color='purple', linestyle='dotted', linewidth=2, label=f'95th Percentile: {token_95th:.0f}')
    
    # Add overall mean as comparison
    overall_token_mean = np.mean(token_counts)
    if overall_token_mean <= ax1.get_xlim()[1]:  # Only show if it fits in the focused view
        ax1.axvline(overall_token_mean, color='darkred', linestyle='dotted', linewidth=2, alpha=0.7, label=f'Overall Mean: {overall_token_mean:.0f}')
    else:
        ax1.text(0.98, 0.95, f'Overall Mean: {overall_token_mean:.0f}\n(beyond chart range)', 
                transform=ax1.transAxes, ha='right', va='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    ax1.legend()
    
    # Top-right: Character focused distribution (95th percentile)
    ax2.hist(char_focused, bins=char_bins, alpha=0.7, color='lightcoral', edgecolor='black')
    ax2.set_title(f'Character Distribution - Focused View (95% of data)\n{len(char_focused)} docs, {char_outliers} outliers excluded')
    ax2.set_xlabel('Number of Characters per Document')
    ax2.set_ylabel('Number of Documents')
    ax2.grid(True, alpha=0.3)
    ax2.axvline(np.mean(char_focused), color='red', linestyle='dashed', linewidth=2, label=f'Focused Mean: {np.mean(char_focused):.0f}')
    ax2.axvline(np.median(char_focused), color='orange', linestyle='dashed', linewidth=2, label=f'Focused Median: {np.median(char_focused):.0f}')
    ax2.axvline(char_95th, color='purple', linestyle='dotted', linewidth=2, label=f'95th Percentile: {char_95th:.0f}')
    
    # Add overall mean as comparison
    overall_char_mean = np.mean(character_counts)
    if overall_char_mean <= ax2.get_xlim()[1]:  # Only show if it fits in the focused view
        ax2.axvline(overall_char_mean, color='darkred', linestyle='dotted', linewidth=2, alpha=0.7, label=f'Overall Mean: {overall_char_mean:.0f}')
    else:
        ax2.text(0.98, 0.95, f'Overall Mean: {overall_char_mean:.0f}\n(beyond chart range)', 
                transform=ax2.transAxes, ha='right', va='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    ax2.legend()
    
    # Get x-axis limits from focused views for consistent scaling
    token_xlim = ax1.get_xlim()
    char_xlim = ax2.get_xlim()
    
    # Create explicit bin edges based on the visible range
    token_bin_edges = np.linspace(token_xlim[0], token_xlim[1], token_bins + 1)
    char_bin_edges = np.linspace(char_xlim[0], char_xlim[1], char_bins + 1)
    
    # Filter data to visible range for plotting
    token_visible = [t for t in token_counts if token_xlim[0] <= t <= token_xlim[1]]
    char_visible = [c for c in character_counts if char_xlim[0] <= c <= char_xlim[1]]
    
    # Count tokens beyond visible range
    tokens_beyond_range = len([t for t in token_counts if t > token_xlim[1]])
    max_token = max(token_counts)
    
    # Bottom-left: Token full range distribution
    ax3.hist(token_visible, bins=token_bin_edges, alpha=0.7, color='steelblue', edgecolor='black')
    ax3.set_xlim(token_xlim)  # Match focused view x-axis
    
    ax3.set_title(f'Token Distribution - Full Range (same scale as focused)\n{len(token_visible)} docs visible, {tokens_beyond_range} beyond range')
    ax3.set_xlabel('Number of Tokens per Document')
    ax3.set_ylabel('Number of Documents')
    ax3.grid(True, alpha=0.3)
    
    # Only show mean/median lines if they're within the visible range
    overall_token_mean = np.mean(token_counts)
    overall_token_median = np.median(token_counts)
    
    if token_xlim[0] <= overall_token_mean <= token_xlim[1]:
        ax3.axvline(overall_token_mean, color='red', linestyle='dashed', linewidth=2, label=f'Overall Mean: {overall_token_mean:.0f}')
    if token_xlim[0] <= overall_token_median <= token_xlim[1]:
        ax3.axvline(overall_token_median, color='orange', linestyle='dashed', linewidth=2, label=f'Overall Median: {overall_token_median:.0f}')
    if token_xlim[0] <= token_95th <= token_xlim[1]:
        ax3.axvline(token_95th, color='purple', linestyle='dotted', linewidth=2, label=f'95th Percentile: {token_95th:.0f}')
    
    # Add annotation for outliers beyond range and hidden statistics
    annotation_text = f'{tokens_beyond_range} docs beyond range\n(max: {max_token:,} tokens)'
    if overall_token_mean > token_xlim[1]:
        annotation_text += f'\nOverall Mean: {overall_token_mean:.0f} (off chart)'
    
    if tokens_beyond_range > 0 or overall_token_mean > token_xlim[1]:
        ax3.text(0.98, 0.85, annotation_text, 
                transform=ax3.transAxes, ha='right', va='top', 
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
    
    ax3.legend()
    
    # Count characters beyond visible range
    chars_beyond_range = len([c for c in character_counts if c > char_xlim[1]])
    max_char = max(character_counts)
    
    # Bottom-right: Character full range distribution
    ax4.hist(char_visible, bins=char_bin_edges, alpha=0.7, color='indianred', edgecolor='black')
    ax4.set_xlim(char_xlim)  # Match focused view x-axis
    
    ax4.set_title(f'Character Distribution - Full Range (same scale as focused)\n{len(char_visible)} docs visible, {chars_beyond_range} beyond range')
    ax4.set_xlabel('Number of Characters per Document')
    ax4.set_ylabel('Number of Documents')
    ax4.grid(True, alpha=0.3)
    
    # Only show mean/median lines if they're within the visible range
    overall_char_mean = np.mean(character_counts)
    overall_char_median = np.median(character_counts)
    
    if char_xlim[0] <= overall_char_mean <= char_xlim[1]:
        ax4.axvline(overall_char_mean, color='red', linestyle='dashed', linewidth=2, label=f'Overall Mean: {overall_char_mean:.0f}')
    if char_xlim[0] <= overall_char_median <= char_xlim[1]:
        ax4.axvline(overall_char_median, color='orange', linestyle='dashed', linewidth=2, label=f'Overall Median: {overall_char_median:.0f}')
    if char_xlim[0] <= char_95th <= char_xlim[1]:
        ax4.axvline(char_95th, color='purple', linestyle='dotted', linewidth=2, label=f'95th Percentile: {char_95th:.0f}')
    
    # Add annotation for outliers beyond range and hidden statistics
    annotation_text = f'{chars_beyond_range} docs beyond range\n(max: {max_char:,} characters)'
    if overall_char_mean > char_xlim[1]:
        annotation_text += f'\nOverall Mean: {overall_char_mean:.0f} (off chart)'
    
    if chars_beyond_range > 0 or overall_char_mean > char_xlim[1]:
        ax4.text(0.98, 0.85, annotation_text, 
                transform=ax4.transAxes, ha='right', va='top', 
                bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.8))
    
    ax4.legend()
    
    plt.tight_layout()
    plt.show()
    
    # Print outlier information
    print(f"\nVisualization displayed with {len(token_counts)} documents.")
    print(f"\nOutlier Analysis:")
    print(f"Token outliers (>95th percentile): {token_outliers} documents (max: {max(token_counts):,} tokens)")
    print(f"Character outliers (>95th percentile): {char_outliers} documents (max: {max(character_counts):,} characters)")
    print(f"95th percentile thresholds: {token_95th:.0f} tokens, {char_95th:.0f} characters")
    print(f"99th percentile thresholds: {token_99th:.0f} tokens, {char_99th:.0f} characters")

def analyze_obsidian_vault():
    if not os.path.exists(VAULT_DIRECTORY):
        print(f"Error: Directory '{VAULT_DIRECTORY}' does not exist.")
        return
    
    if not os.path.isdir(VAULT_DIRECTORY):
        print(f"Error: '{VAULT_DIRECTORY}' is not a directory.")
        return
    
    markdown_files = []
    character_counts = []
    token_counts = []
    file_data = []  # Store (file_path, token_count, char_count) for each file
    
    for root, dirs, files in os.walk(VAULT_DIRECTORY):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                markdown_files.append(file_path)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        char_count = len(content)
                        character_counts.append(char_count)
                        
                        if TIKTOKEN_AVAILABLE:
                            try:
                                tokens = encoding.encode(content)
                                token_count = len(tokens)
                                token_counts.append(token_count)
                            except Exception as e:
                                print(f"Warning: Could not tokenize file '{file_path}': {e}")
                                token_count = 0
                                token_counts.append(token_count)
                        else:
                            token_count = char_count // 4
                            token_counts.append(token_count)
                        
                        # Store file data for outlier analysis
                        file_data.append((file_path, token_count, char_count))
                            
                except Exception as e:
                    print(f"Warning: Could not read file '{file_path}': {e}")
                    continue
    
    if not character_counts:
        print("No markdown files found in the vault directory.")
        return
    
    total_characters = sum(character_counts)
    total_documents = len(character_counts)
    average_characters = total_characters / total_documents
    min_characters = min(character_counts)
    max_characters = max(character_counts)
    
    total_tokens = sum(token_counts)
    average_tokens = total_tokens / total_documents
    min_tokens = min(token_counts)
    max_tokens = max(token_counts)
    
    print("Obsidian Vault Analysis Results")
    print("=" * 50)
    print(f"\nTotal documents analyzed: {total_documents:,}")
    
    print(f"\nOVERALL STATISTICS (All Documents Including Outliers):")
    print("-" * 55)
    print("Character Metrics:")
    print(f"  Total characters: {total_characters:,}")
    print(f"  Average characters per document: {average_characters:,.1f}")
    print(f"  Minimum characters: {min_characters:,}")
    print(f"  Maximum characters: {max_characters:,}")
    
    token_label = "Token Metrics (tiktoken cl100k_base):" if TIKTOKEN_AVAILABLE else "Token Metrics (estimated):"
    print(f"\n{token_label}")
    print(f"  Total tokens: {total_tokens:,.0f}")
    print(f"  Average tokens per document: {average_tokens:,.1f}")
    print(f"  Minimum tokens: {min_tokens:,.0f}")
    print(f"  Maximum tokens: {max_tokens:,.0f}")
    
    if MATPLOTLIB_AVAILABLE and token_counts:
        # Calculate focused statistics (95th percentile)
        token_95th = np.percentile(token_counts, 95)
        char_95th = np.percentile(character_counts, 95)
        token_focused = [t for t in token_counts if t <= token_95th]
        char_focused = [c for c in character_counts if c <= char_95th]
        
        print(f"\nFOCUSED STATISTICS (95% of Documents, Outliers Excluded):")
        print("-" * 55)
        print(f"Documents in focused view: {len(token_focused):,}")
        print(f"Outliers excluded: {len(token_counts) - len(token_focused):,}")
        
        print("Character Metrics (Focused):")
        print(f"  Average characters per document: {np.mean(char_focused):,.1f}")
        print(f"  Median characters: {np.median(char_focused):,.0f}")
        print(f"  Range: {min(char_focused):,} - {max(char_focused):,}")
        
        print("Token Metrics (Focused):")
        print(f"  Average tokens per document: {np.mean(token_focused):,.1f}")
        print(f"  Median tokens: {np.median(token_focused):,.0f}")
        print(f"  Range: {min(token_focused):,} - {max(token_focused):,}")
        
        # Overall distribution statistics
        token_percentiles = np.percentile(token_counts, [25, 50, 75, 95, 99])
        char_percentiles = np.percentile(character_counts, [25, 50, 75, 95, 99])
        
        print(f"\nDISTRIBUTION ANALYSIS:")
        print("-" * 55)
        print(f"Token percentiles (25th, 50th, 75th, 95th, 99th):")
        print(f"  {token_percentiles[0]:,.0f}, {token_percentiles[1]:,.0f}, {token_percentiles[2]:,.0f}, {token_percentiles[3]:,.0f}, {token_percentiles[4]:,.0f}")
        print(f"Character percentiles (25th, 50th, 75th, 95th, 99th):")
        print(f"  {char_percentiles[0]:,.0f}, {char_percentiles[1]:,.0f}, {char_percentiles[2]:,.0f}, {char_percentiles[3]:,.0f}, {char_percentiles[4]:,.0f}")
        
        # Impact of outliers
        outlier_token_sum = sum(t for t in token_counts if t > token_95th)
        outlier_char_sum = sum(c for c in character_counts if c > char_95th)
        
        print(f"\nOUTLIER IMPACT:")
        print("-" * 55)
        print(f"Top 5% of documents contribute:")
        print(f"  {(outlier_token_sum / total_tokens * 100):.1f}% of all tokens")
        print(f"  {(outlier_char_sum / total_characters * 100):.1f}% of all characters")
        print(f"Difference between overall and focused averages:")
        print(f"  Tokens: {average_tokens - np.mean(token_focused):,.0f} ({((average_tokens / np.mean(token_focused) - 1) * 100):.1f}% higher)")
        print(f"  Characters: {average_characters - np.mean(char_focused):,.0f} ({((average_characters / np.mean(char_focused) - 1) * 100):.1f}% higher)")
        
        # Export outliers to CSV
        export_outliers_to_csv(file_data, token_95th, char_95th)
    
    create_token_distribution_chart(token_counts, character_counts)

if __name__ == "__main__":
    analyze_obsidian_vault()
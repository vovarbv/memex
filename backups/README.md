# Memex Backup Strategy

This directory is intended for storing backups of your Memex configuration and data files.

## Example Backup

The `example_manual_backup/` directory demonstrates the key files you should consider backing up:

- **memory.toml** - Your main configuration file
- **TASKS.yaml** - Your task definitions and progress

## Recommended Backup Strategy

### Critical Files to Back Up Regularly:

1. **Configuration & Data Files:**
   - `memory.toml` - Main configuration
   - `docs/TASKS.yaml` - Your tasks and progress
   - `docs/PREFERENCES.yaml` - Your AI assistant preferences

2. **Vector Store (Optional):**
   - `.cursor/vecstore/` - Can be regenerated but backup saves time
   - Note: This can be large, so consider frequency vs. storage

### Backup Methods

You can implement backups using:

1. **Manual Backups:**
   ```bash
   # Create a timestamped backup
   cp memory.toml backups/backup_$(date +%Y%m%d_%H%M%S)/
   cp docs/TASKS.yaml backups/backup_$(date +%Y%m%d_%H%M%S)/
   cp docs/PREFERENCES.yaml backups/backup_$(date +%Y%m%d_%H%M%S)/
   ```

2. **Automated Backups:**
   - Use the Settings tab in Memex Hub UI
   - Set up a cron job or scheduled task
   - Integrate with your existing backup solution

3. **Version Control:**
   - Consider using git branches for configuration experiments
   - Tag stable configurations

## Important Notes

- The vector store (`.cursor/vecstore/`) can always be regenerated using `index_codebase`
- Focus on backing up files that contain your unique work and preferences
- Test your restore process periodically to ensure backups are valid

## Storage Recommendations

- Keep at least 3-5 recent backups
- Store critical backups off-site or in cloud storage
- Name backups with timestamps for easy identification
- Document any special restore procedures needed
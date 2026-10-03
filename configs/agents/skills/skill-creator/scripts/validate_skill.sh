#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s <skill-directory>\n' "$0" >&2
  exit 2
fi

if ! command -v ruby >/dev/null 2>&1; then
  printf 'Validation requires Ruby with its standard YAML library.\n' >&2
  exit 2
fi

ruby - "$1" <<'RUBY'
require "pathname"
require "yaml"

ALLOWED_FIELDS = %w[
  name
  description
  license
  allowed-tools
  metadata
  compatibility
  disable-model-invocation
].freeze

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1_024
MAX_COMPATIBILITY_LENGTH = 500

errors = []
skill_dir = Pathname.new(ARGV.fetch(0)).expand_path
skill_file = skill_dir.join("SKILL.md")

unless skill_dir.directory?
  errors << "Not a skill directory: #{skill_dir}"
end

unless skill_file.file?
  errors << "Missing required file: #{skill_file}"
end

if errors.empty?
  content = skill_file.read(encoding: "UTF-8")
  lines = content.lines

  if lines.first&.strip != "---"
    errors << "SKILL.md must start with YAML frontmatter (---)"
  else
    closing_offset = lines.drop(1).index { |line| line.strip == "---" }

    if closing_offset.nil?
      errors << "SKILL.md frontmatter must end with ---"
    else
      closing_index = closing_offset + 1
      frontmatter = lines[1...closing_index].join
      body = lines[(closing_index + 1)..].to_a.join.strip

      begin
        metadata = YAML.safe_load(frontmatter, permitted_classes: [], aliases: false)
      rescue Psych::Exception => error
        errors << "Invalid YAML frontmatter: #{error.message.lines.first.strip}"
        metadata = nil
      end

      if !metadata.nil? && !metadata.is_a?(Hash)
        errors << "SKILL.md frontmatter must be a YAML mapping"
      elsif metadata.is_a?(Hash)
        metadata = metadata.transform_keys(&:to_s)
        unexpected_fields = metadata.keys - ALLOWED_FIELDS
        unless unexpected_fields.empty?
          errors << "Unexpected frontmatter fields: #{unexpected_fields.sort.join(', ')}"
        end

        name = metadata["name"]
        if !name.is_a?(String) || name.strip.empty?
          errors << "Field 'name' must be a non-empty string"
        else
          name = name.strip
          errors << "Field 'name' exceeds #{MAX_NAME_LENGTH} characters" if name.length > MAX_NAME_LENGTH
          errors << "Field 'name' must use lowercase letters, numbers, and single hyphens" unless name.match?(/\A[a-z0-9]+(?:-[a-z0-9]+)*\z/)
          errors << "Directory name '#{skill_dir.basename}' must match skill name '#{name}'" if skill_dir.basename.to_s != name
        end

        description = metadata["description"]
        if !description.is_a?(String) || description.strip.empty?
          errors << "Field 'description' must be a non-empty string"
        elsif description.length > MAX_DESCRIPTION_LENGTH
          errors << "Field 'description' exceeds #{MAX_DESCRIPTION_LENGTH} characters"
        end

        compatibility = metadata["compatibility"]
        if !compatibility.nil? && !compatibility.is_a?(String)
          errors << "Field 'compatibility' must be a string"
        elsif compatibility&.length.to_i > MAX_COMPATIBILITY_LENGTH
          errors << "Field 'compatibility' exceeds #{MAX_COMPATIBILITY_LENGTH} characters"
        end

        %w[license allowed-tools].each do |field|
          value = metadata[field]
          errors << "Field '#{field}' must be a string" if !value.nil? && !value.is_a?(String)
        end

        disable_model_invocation = metadata["disable-model-invocation"]
        unless disable_model_invocation.nil? || [true, false].include?(disable_model_invocation)
          errors << "Field 'disable-model-invocation' must be a boolean"
        end

        metadata_values = metadata["metadata"]
        if !metadata_values.nil? && !metadata_values.is_a?(Hash)
          errors << "Field 'metadata' must be a mapping"
        elsif metadata_values.is_a?(Hash)
          metadata_values.each do |key, value|
            errors << "Metadata key and value must be strings: #{key.inspect}" unless key.is_a?(String) && value.is_a?(String)
          end
        end
      end

      errors << "SKILL.md must contain instructions after the frontmatter" if body.empty?
    end
  end
end

if errors.empty?
  puts "Valid skill: #{skill_dir}"
  exit 0
end

errors.each { |error| warn "ERROR: #{error}" }
exit 1
RUBY

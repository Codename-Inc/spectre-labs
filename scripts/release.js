#!/usr/bin/env node

/**
 * Release script for spectre-labs
 *
 * Bumps versions in:
 * - sparks/.claude-plugin/plugin.json
 * - sparks/.claude-plugin/marketplace.json
 * - build-loop/pyproject.toml
 */

import { createInterface } from 'readline';
import { readFileSync, writeFileSync } from 'fs';
import { execSync } from 'child_process';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');

// Component paths
const SPARKS_PLUGIN_PATH = join(ROOT, 'sparks/.claude-plugin/plugin.json');
const SPARKS_MARKETPLACE_PATH = join(ROOT, '.claude-plugin/marketplace.json');
const BUILD_LOOP_PYPROJECT_PATH = join(ROOT, 'build-loop/pyproject.toml');

const rl = createInterface({
  input: process.stdin,
  output: process.stdout,
});

const ask = (q) => new Promise((resolve) => rl.question(q, resolve));

const readJSON = (path) => JSON.parse(readFileSync(path, 'utf8'));
const writeJSON = (path, data) => writeFileSync(path, JSON.stringify(data, null, 2) + '\n');

const readTOML = (path) => {
  const content = readFileSync(path, 'utf8');
  const versionMatch = content.match(/^version\s*=\s*"([^"]+)"/m);
  return {
    content,
    version: versionMatch ? versionMatch[1] : 'unknown',
  };
};

const writeTOML = (path, content, newVersion) => {
  const updated = content.replace(
    /^version\s*=\s*"[^"]+"/m,
    `version = "${newVersion}"`
  );
  writeFileSync(path, updated);
};

const bumpVersion = (version, type) => {
  if (!version || version === 'unknown') return version;
  const [major, minor, patch] = version.split('.').map(Number);
  switch (type) {
    case 'major': return `${major + 1}.0.0`;
    case 'minor': return `${major}.${minor + 1}.0`;
    case 'patch': return `${major}.${minor}.${patch + 1}`;
    default: return version;
  }
};

const run = (cmd) => {
  console.log(`\n$ ${cmd}`);
  try {
    execSync(cmd, { stdio: 'inherit', cwd: ROOT });
    return true;
  } catch (e) {
    console.error(`Command failed: ${cmd}`);
    return false;
  }
};

async function main() {
  console.log('\n🚀 SPECTRE Labs Release Script\n');

  // Read current versions
  const sparksPlugin = readJSON(SPARKS_PLUGIN_PATH);
  const sparksMarketplace = readJSON(SPARKS_MARKETPLACE_PATH);
  const buildLoop = readTOML(BUILD_LOOP_PYPROJECT_PATH);

  const components = [
    {
      name: 'sparks',
      version: sparksPlugin.version,
      type: 'plugin',
    },
    {
      name: 'build-loop',
      version: buildLoop.version,
      type: 'python',
    },
  ];

  // Display current versions
  console.log('Current versions:');
  const maxNameLen = Math.max(...components.map((c) => c.name.length));
  for (const comp of components) {
    console.log(`  ${comp.name.padEnd(maxNameLen)}  ${comp.version}`);
  }
  console.log();

  // Build component selection menu
  console.log('Which component(s) to release?');
  components.forEach((c, i) => {
    console.log(`  ${i + 1}. ${c.name} only`);
  });
  const allOption = components.length + 1;
  console.log(`  ${allOption}. all (recommended)\n`);

  const compChoice = await ask(`Choice [${allOption}]: `);
  const choice = parseInt(compChoice.trim() || String(allOption), 10);

  let selectedComponents;
  if (choice === allOption) {
    selectedComponents = components;
  } else if (choice >= 1 && choice <= components.length) {
    selectedComponents = [components[choice - 1]];
  } else {
    console.log('Invalid choice. Exiting.');
    rl.close();
    process.exit(1);
  }

  // Ask version bump for each selected component
  const askBumpType = async (name, currentVersion) => {
    console.log(`\n${name} (${currentVersion}):`);
    console.log(`  1. patch → ${bumpVersion(currentVersion, 'patch')}`);
    console.log(`  2. minor → ${bumpVersion(currentVersion, 'minor')}`);
    console.log(`  3. major → ${bumpVersion(currentVersion, 'major')}`);
    console.log(`  4. skip (no change)`);

    const choice = await ask('Choice [1]: ');
    const type = { '1': 'patch', '2': 'minor', '3': 'major', '4': 'skip' }[choice.trim() || '1'] || 'patch';
    return type === 'skip' ? null : bumpVersion(currentVersion, type);
  };

  // Collect version bumps
  console.log('\n--- Version Bumps ---');
  for (const comp of selectedComponents) {
    comp.newVersion = await askBumpType(comp.name, comp.version);
  }

  // Show summary
  console.log('\n--- Release Summary ---');
  let hasChanges = false;
  for (const comp of selectedComponents) {
    if (comp.newVersion) {
      console.log(`  ${comp.name}: ${comp.version} → ${comp.newVersion}`);
      hasChanges = true;
    } else {
      console.log(`  ${comp.name}: (skip)`);
    }
  }

  if (!hasChanges) {
    console.log('\nNo changes selected. Exiting.');
    rl.close();
    process.exit(0);
  }

  // Confirm
  const confirm = await ask('\nProceed with release? [Y/n]: ');
  if (confirm.toLowerCase() === 'n') {
    console.log('Aborted.');
    rl.close();
    process.exit(0);
  }

  // Update version files
  console.log('\nUpdating version files...');

  for (const comp of selectedComponents) {
    if (!comp.newVersion) continue;

    if (comp.name === 'sparks') {
      // Update plugin.json
      sparksPlugin.version = comp.newVersion;
      writeJSON(SPARKS_PLUGIN_PATH, sparksPlugin);
      console.log(`  ✓ sparks/.claude-plugin/plugin.json → ${comp.newVersion}`);

      // Update marketplace.json (both top-level version and plugin entry version)
      sparksMarketplace.version = comp.newVersion;
      const marketplacePlugin = sparksMarketplace.plugins.find((p) => p.name === 'sparks');
      if (marketplacePlugin) {
        marketplacePlugin.version = comp.newVersion;
      }
      writeJSON(SPARKS_MARKETPLACE_PATH, sparksMarketplace);
      console.log(`  ✓ sparks/.claude-plugin/marketplace.json → ${comp.newVersion}`);
    }

    if (comp.name === 'build-loop') {
      writeTOML(BUILD_LOOP_PYPROJECT_PATH, buildLoop.content, comp.newVersion);
      console.log(`  ✓ build-loop/pyproject.toml → ${comp.newVersion}`);
    }
  }

  // Git operations
  console.log('\nGit operations...');

  // Build version string for commit/tag
  const versions = selectedComponents
    .filter((c) => c.newVersion)
    .map((c) => `${c.name}@${c.newVersion}`);
  const commitMsg = `release: ${versions.join(', ')}`;

  // Use highest version for tag
  const tagVersion = selectedComponents
    .map((c) => c.newVersion)
    .filter(Boolean)
    .sort()
    .pop();
  const tagName = `v${tagVersion}`;

  run('git add -A');
  run(`git commit -m "${commitMsg}"`);

  const pushConfirm = await ask('\nPush to remote and create tag? [Y/n]: ');
  if (pushConfirm.toLowerCase() !== 'n') {
    run('git push');
    run(`git tag ${tagName}`);
    run('git push --tags');
    console.log(`\n✅ Released ${tagName}`);
  } else {
    console.log(`\n✅ Committed locally as ${tagName} (not pushed)`);
  }

  rl.close();
}

main().catch((err) => {
  console.error(err);
  rl.close();
  process.exit(1);
});

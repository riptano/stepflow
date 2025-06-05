#![allow(clippy::print_stdout)]
use crate::cli::{OutputFormat, create_executor, load_config};
use crate::{MainError, Result};
use error_stack::ResultExt as _;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use stepflow_core::{component::ComponentInfo, workflow::Component};
use stepflow_plugin::Plugin as _;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ComponentDetails {
    /// The component identifier (URL)
    pub component: Component,
    /// Information about the component including schemas
    #[serde(flatten)]
    pub info: ComponentInfo,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ComponentList {
    pub components: Vec<ComponentDetails>,
}

/// List all available components from a stepflow config.
pub async fn list_components(config_path: Option<PathBuf>, format: OutputFormat) -> Result<()> {
    // Load config using the standard resolution logic
    let config = load_config(None, config_path)?;

    // Create executor to instantiate plugins
    let executor = create_executor(config).await?;

    // Get all registered plugins and query their components
    let mut all_components = Vec::new();

    // Get the list of plugins from the executor
    for (_protocol, plugin) in executor.list_plugins().await {
        // List components available from this plugin
        let components = plugin
            .list_components()
            .await
            .change_context(MainError::PluginCommunication)?;

        // For each component, get detailed information
        for component in components {
            let info = plugin
                .component_info(&component)
                .await
                .change_context(MainError::PluginCommunication)?;

            all_components.push(ComponentDetails { component, info });
        }
    }

    // Sort components by their URL for consistent output
    all_components.sort_by(|a, b| a.component.url().as_str().cmp(b.component.url().as_str()));

    let component_list = ComponentList {
        components: all_components,
    };

    // Output in the requested format
    match format {
        OutputFormat::Pretty => print_pretty(&component_list),
        OutputFormat::Json => {
            let json = serde_json::to_string_pretty(&component_list)
                .change_context(MainError::SerializationError)?;
            println!("{}", json);
        }
        OutputFormat::Yaml => {
            let yaml = serde_yaml_ng::to_string(&component_list)
                .change_context(MainError::SerializationError)?;
            println!("{}", yaml);
        }
    }

    Ok(())
}

fn print_pretty(component_list: &ComponentList) {
    if component_list.components.is_empty() {
        println!("No components found.");
        return;
    }

    println!("Available Components:");
    println!("====================");

    for component in &component_list.components {
        println!();
        println!("Component: {}", component.component.url());

        // Print input schema
        println!("  Input Schema:");
        let input_schema_str = serde_json::to_string_pretty(&component.info.input_schema)
            .unwrap_or_else(|_| "Error serializing schema".to_string());
        for line in input_schema_str.lines() {
            println!("    {}", line);
        }

        // Print output schema
        println!("  Output Schema:");
        let output_schema_str = serde_json::to_string_pretty(&component.info.output_schema)
            .unwrap_or_else(|_| "Error serializing schema".to_string());
        for line in output_schema_str.lines() {
            println!("    {}", line);
        }
    }

    println!();
    println!("Total components: {}", component_list.components.len());
}

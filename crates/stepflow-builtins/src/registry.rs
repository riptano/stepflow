use std::{
    collections::HashMap,
    sync::{Arc, LazyLock},
};
use stepflow_core::workflow::{Component, ComponentKey};
use stepflow_plugin::{PluginError, Result};

use crate::{
    BuiltinComponent, DynBuiltinComponent,
    blob::{GetBlobComponent, PutBlobComponent},
    eval::EvalComponent,
    load_file::LoadFileComponent,
    messages::CreateMessagesComponent,
    openai::OpenAIComponent,
};

#[derive(Default)]
struct Registry {
    components: HashMap<ComponentKey<'static>, Arc<DynBuiltinComponent<'static>>>,
}

impl Registry {
    pub fn register<C: BuiltinComponent + 'static>(
        &mut self,
        host: &'static str,
        path: &'static str,
        component: C,
    ) {
        let key = (Some(host), path);
        let component = DynBuiltinComponent::boxed(component);
        let component = Arc::from(component);
        self.components.insert(key, component);
    }
}

static REGISTRY: LazyLock<Registry> = LazyLock::new(|| {
    let mut registry = Registry::default();
    // For URLs like "builtins://component_name", the host is "component_name" and path is ""
    registry.register("openai", "", OpenAIComponent::new("gpt-3.5-turbo"));
    registry.register("create_messages", "", CreateMessagesComponent);
    registry.register("eval", "", EvalComponent::new());
    registry.register("load_file", "", LoadFileComponent);
    registry.register("put_blob", "", PutBlobComponent::new());
    registry.register("get_blob", "", GetBlobComponent::new());
    registry
});

pub fn get_component(component: &Component) -> Result<Arc<DynBuiltinComponent<'_>>> {
    // For URLs like "builtins://eval", the host is "eval" and path is ""
    // The components are registered with (host, path) keys
    let key = (component.host(), component.path());

    let component = REGISTRY
        .components
        .get(&key)
        .ok_or_else(|| PluginError::UnknownComponent(component.clone()))?;

    Ok(component.clone())
}

pub fn list_components() -> Vec<Component> {
    REGISTRY
        .components
        .keys()
        .map(|(host, path)| {
            let url = if path.is_empty() {
                format!("builtins://{}", host.unwrap_or(""))
            } else {
                format!("builtins://{}/{}", host.unwrap_or(""), path)
            };
            Component::new(url.parse().expect("Invalid URL"))
        })
        .collect()
}

// Licensed to the Apache Software Foundation (ASF) under one or more contributor license agreements.
// See the NOTICE file distributed with this work for additional information regarding copyright
// ownership.  The ASF licenses this file to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance with the License.  You may obtain a
// copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software distributed under the License
// is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
// or implied.  See the License for the specific language governing permissions and limitations under
// the License.

use stepflow_core::{FlowResult, component::ComponentInfo, workflow::ValueRef};
use stepflow_plugin::ExecutionContext;

mod blob;
mod error;
mod eval;
mod iterate;
mod load_file;
mod map;
mod messages;
#[cfg(test)]
mod mock_context;
mod openai;
mod plugin;
mod registry;

use error::Result;
pub use plugin::{BuiltinPluginConfig, Builtins};

#[trait_variant::make(Send)]
#[dynosaur::dynosaur(DynBuiltinComponent = dyn BuiltinComponent)]
pub(crate) trait BuiltinComponent: Send + Sync {
    fn component_info(&self) -> Result<ComponentInfo>;

    async fn execute(&self, context: ExecutionContext, input: ValueRef) -> Result<FlowResult>;
}

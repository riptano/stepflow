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

//! Schema manipulation and validation types.

use schemars::{JsonSchema, Schema};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

/// Type alias for a shared schema reference.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[repr(transparent)]
pub struct SchemaRef(Arc<Schema>);

impl JsonSchema for SchemaRef {
    fn schema_name() -> std::borrow::Cow<'static, str> {
        "Schema".into()
    }

    fn json_schema(_generator: &mut schemars::SchemaGenerator) -> schemars::Schema {
        schemars::json_schema!({
             "$ref": _generator.settings().meta_schema,
        })
    }
}

impl From<Schema> for SchemaRef {
    fn from(schema: Schema) -> Self {
        SchemaRef(Arc::new(schema))
    }
}

impl AsRef<Schema> for SchemaRef {
    fn as_ref(&self) -> &Schema {
        &self.0
    }
}

impl utoipa::PartialSchema for SchemaRef {
    fn schema() -> utoipa::openapi::RefOr<utoipa::openapi::schema::Schema> {
        // OpenAPI doesn't allow external references, so there is no good way to
        // enforce that this is consistent with the JSON schema.
        let schema = utoipa::openapi::ObjectBuilder::new()
            .description(Some("A valid JSON Schema object."))
            .build();
        utoipa::openapi::RefOr::T(utoipa::openapi::Schema::Object(schema))
    }
}

impl utoipa::ToSchema for SchemaRef {}

impl SchemaRef {
    /// Create a schema reference from a type that implements JsonSchema.
    pub fn for_type<T: JsonSchema>() -> Self {
        // TODO: Look into caching this? We could use the `schema_id`?
        let mut generator = schemars::SchemaGenerator::default();
        let schema = T::json_schema(&mut generator);
        schema.into()
    }

    pub fn parse_json(s: &str) -> Result<Self, serde_json::Error> {
        let schema = serde_json::from_str::<Schema>(s)?;
        Ok(schema.into())
    }
}

use std::fs::File;
use std::io::BufReader;

use error_stack::ResultExt as _;
use serde::Deserialize;
use stepflow_execution::execute;
use stepflow_plugin::{Plugin, Plugins};
use stepflow_plugin_protocol::stdio::{Client, StdioPlugin};
use stepflow_plugin_testing::{MockComponentBehavior, MockPlugin};
use stepflow_workflow::Value;
use tracing_subscriber::{EnvFilter, layer::SubscriberExt as _, util::SubscriberInitExt as _};

static INIT_TEST_LOGGING: std::sync::Once = std::sync::Once::new();

/// Makes sure logging is initialized for test.
///
/// This needs to be called on each test.
pub fn init_test_logging() {
    INIT_TEST_LOGGING.call_once(|| {
        // We don't use a test writer for end to end testts.
        let fmt_layer = tracing_subscriber::fmt::layer();

        tracing_subscriber::registry()
            .with(EnvFilter::new("stepflow_=trace,info"))
            .with(fmt_layer)
            .with(tracing_error::ErrorLayer::default())
            .try_init()
            .unwrap();
    });
}

#[derive(Deserialize)]
struct TestFlow {
    #[serde(flatten)]
    flow: stepflow_workflow::Flow,
    test_cases: Vec<TestCase>,
}

#[derive(Deserialize)]
struct TestCase {
    input: serde_json::Value,
    #[serde(default)]
    expect_failure: bool,
}

fn create_mock_plugin() -> MockPlugin {
    let mut mock_plugin = MockPlugin::new("mock");
    mock_plugin
        .mock_component("mock://one_output")
        .behavior(
            Value::new(serde_json::json!({ "input": "a" })),
            MockComponentBehavior::Valid {
                output: Value::new(serde_json::json!({ "output": "b" })),
            },
        )
        .behavior(
            Value::new(serde_json::json!({ "input": "hello" })),
            MockComponentBehavior::Valid {
                output: Value::new(serde_json::json!({ "output": "world" })),
            },
        );
    mock_plugin
        .mock_component("mock://two_outputs")
        .behavior(
            Value::new(serde_json::json!({ "input": "b" })),
            MockComponentBehavior::Valid {
                output: Value::new(serde_json::json!({ "x": 1, "y": 2 })),
            },
        )
        .behavior(
            Value::new(serde_json::json!({ "input": "world" })),
            MockComponentBehavior::Valid {
                output: Value::new(serde_json::json!({ "x": 2, "y": 8 })),
            },
        );
    mock_plugin
}

/// Simple error we can wrap any other errors in.
#[derive(Debug, thiserror::Error)]
#[error("test error")]
struct TestError;

async fn create_python_plugin() -> error_stack::Result<StdioPlugin, TestError> {
    let uv = which::which("uv").change_context(TestError)?;
    tracing::info!("Found uv at {uv:?}");

    // Determine the path to the `sdks/python` directory from the CARGO_MANIFEST_DIR.
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").change_context(TestError)?;
    let python_dir = std::path::Path::new(&manifest_dir)
        .parent()
        .ok_or(TestError)?
        .parent()
        .ok_or(TestError)?
        .join("sdks")
        .join("python");
    let python_dir = python_dir.to_str().ok_or(TestError)?;

    let client = Client::builder(uv)
        .args(["--project", python_dir, "run", "stepflow_sdk"])
        .build()
        .await
        .change_context(TestError)?;

    let plugin = StdioPlugin::new(client.handle());
    plugin.init().await.change_context(TestError)?;
    Ok(plugin)
}

fn run_tests(plugins: Plugins, rt: tokio::runtime::Handle) {
    insta::glob!("flows/*.yaml", |path| {
        rt.block_on(async {
            let file = File::open(path).unwrap();
            let reader = BufReader::new(file);
            let TestFlow { flow, test_cases } =
                serde_yml::from_reader::<_, TestFlow>(reader).unwrap();

            let mut settings = insta::Settings::clone_current();
            settings.set_input_file(path);

            for (index, test_case) in test_cases.into_iter().enumerate() {
                settings.set_description(format!("case {index}"));
                settings.set_info(&test_case.input);

                let result = execute(&plugins, &flow, Value::new(test_case.input)).await;
                if test_case.expect_failure {
                    let result = result.unwrap_err();
                    settings.bind(|| {
                        insta::assert_yaml_snapshot!(result);
                    });
                } else {
                    let result = result.unwrap();
                    settings.bind(|| {
                        insta::assert_yaml_snapshot!(result);
                    });
                }
            }
        })
    });
}

#[tokio::test(flavor = "multi_thread")]
async fn execute_flows() {
    init_test_logging();

    let mut plugins = Plugins::new();

    plugins.register("mock".to_owned(), create_mock_plugin());
    plugins.register("python".to_owned(), create_python_plugin().await.unwrap());

    let rt = tokio::runtime::Handle::current();

    let handle = rt.clone().spawn_blocking(|| run_tests(plugins, rt));
    handle.await.unwrap();
}

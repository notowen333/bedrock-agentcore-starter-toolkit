import * as cdk from 'aws-cdk-lib/core';
import { Construct } from 'constructs/lib/construct';
import * as bedrockagentcore from 'aws-cdk-lib/aws-bedrockagentcore';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda'
import * as cognito from 'aws-cdk-lib/aws-cognito';
import { BaseStackProps } from '../types';
import * as path from 'path';

export interface AgentCoreStackProps extends BaseStackProps {
    imageUri: string
}

export class AgentCoreStack extends cdk.Stack {
    readonly agentCoreRuntime: bedrockagentcore.CfnRuntime;
    readonly agentCoreGateway: bedrockagentcore.CfnGateway;
    readonly agentCoreMemory: bedrockagentcore.CfnMemory;
    readonly mcpLambda: lambda.Function;

    constructor(scope: Construct, id: string, props: AgentCoreStackProps) {
        super(scope, id, props);

        const region = cdk.Stack.of(this).region;
        const accountId = cdk.Stack.of(this).account;
        /*****************************
        * AgentCore Gateway
        ******************************/

        this.mcpLambda = new lambda.Function(this, `${props.appName}-McpLambda`, {
            runtime: lambda.Runtime.PYTHON_3_12,
            handler: "handler.lambda_handler",
            code: lambda.AssetCode.fromAsset(path.join(__dirname, '../../../mcp/lambda'))
        });

        const agentCoreGatewayRole = new iam.Role(this, `${props.appName}-AgentCoreGatewayRole`, {
            assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
            description: 'IAM role for Bedrock AgentCore Runtime',
        });

        this.mcpLambda.grantInvoke(agentCoreGatewayRole);

        // Create gateway resource
        // Cognito resources
        const cognitoUserPool = new cognito.UserPool(this, `${props.appName}-CognitoUserPool`);

        // create resource server to work with client credentials auth flow
        const cognitoResourceServerScope = {
            scopeName: 'basic',
            scopeDescription: 'Basic access to echooo',
        };

        const cognitoResourceServer = cognitoUserPool.addResourceServer(`${props.appName}-CognitoResourceServer`, {
            identifier: `${props.appName}-CognitoResourceServer`,
            scopes: [cognitoResourceServerScope],
        });

        const cognitoAppClient = new cognito.UserPoolClient(this, `${props.appName}-CognitoAppClient`, {
            userPool: cognitoUserPool,
            generateSecret: true,
            oAuth: {
                flows: {
                    clientCredentials: true,
                },
                scopes: [cognito.OAuthScope.resourceServer(cognitoResourceServer, cognitoResourceServerScope)],
            },
            supportedIdentityProviders: [cognito.UserPoolClientIdentityProvider.COGNITO],
        });
        const cognitoDomain = cognitoUserPool.addDomain(`${props.appName}-CognitoDomain`, {
            cognitoDomain: {
                domainPrefix: `${props.appName.toLowerCase()}-${region}`,
            },
        });
        const cognitoTokenUrl = cognitoDomain.baseUrl() + '/oauth2/token';

        this.agentCoreGateway = new bedrockagentcore.CfnGateway(this, `${props.appName}-AgentCoreGateway`, {
            name: `${props.appName}-AgentCoreGateway`,
            protocolType: "MCP",
            roleArn: agentCoreGatewayRole.roleArn,
            authorizerType: "CUSTOM_JWT",
            authorizerConfiguration: {
                customJwtAuthorizer: {
                discoveryUrl:
                    'https://cognito-idp.' +
                    region +
                    '.amazonaws.com/' +
                    cognitoUserPool.userPoolId +
                    '/.well-known/openid-configuration',
                allowedClients: [cognitoAppClient.userPoolClientId],
                },
            },
        });

        new bedrockagentcore.CfnGatewayTarget(this, `${props.appName}-AgentCoreGatewayLambdaTarget`, {
            name: `${props.appName}-AgentCoreGatewayLambdaTarget`,
            gatewayIdentifier: this.agentCoreGateway.attrGatewayIdentifier,
            credentialProviderConfigurations: [
                {
                    credentialProviderType: "GATEWAY_IAM_ROLE",
                },
            ],
            targetConfiguration: {
                mcp: {
                    lambda: {
                        lambdaArn: this.mcpLambda.functionArn,
                        toolSchema: {
                            inlinePayload: [
                                {
                                    name: "placeholder_tool",
                                    description: "No-op tool that demonstrates passing arguments",
                                    inputSchema: {
                                        type: "object",
                                        properties: {
                                            string_param: { type: 'string', description: 'Example string parameter' },
                                            int_param: { type: 'integer', description: 'Example integer parameter' },
                                            float_array_param: {
                                                type: 'array',
                                                description: 'Example float array parameter',
                                                items: {
                                                    type: 'number',
                                                }
                                            }
                                        },
                                        required: []
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        })

        /*****************************
        * AgentCore Memory
        ******************************/

        this.agentCoreMemory = new bedrockagentcore.CfnMemory(this, `${props.appName}-AgentCoreMemory`, {
            name: "create_agent_memory",
            eventExpiryDuration: 30,
            description: "Memory resource with 30 days event expiry",
            memoryStrategies: [
                // can take a built-in strategy from https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/built-in-strategies.html or define a custom one
            ],
        });

        /*****************************
        * AgentCore Runtime
        ******************************/

        // taken from https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html#runtime-permissions-execution
        const runtimePolicy = new iam.PolicyDocument({
            statements: [
                new iam.PolicyStatement({
                    sid: 'ECRImageAccess',
                    effect: iam.Effect.ALLOW,
                    actions: ['ecr:BatchGetImage', 'ecr:GetDownloadUrlForLayer'],
                    resources: [
                        `arn:aws:ecr:${region}:${accountId}:repository/*`,
                    ],
                }),
                new iam.PolicyStatement({
                    effect: iam.Effect.ALLOW,
                    actions: ['logs:DescribeLogStreams', 'logs:CreateLogGroup'],
                    resources: [
                        `arn:aws:logs:${region}:${accountId}:log-group:/aws/bedrock-agentcore/runtimes/*`,
                    ],
                }),
                new iam.PolicyStatement({
                    effect: iam.Effect.ALLOW,
                    actions: ['logs:DescribeLogGroups'],
                    resources: [
                        `arn:aws:logs:${region}:${accountId}:log-group:*`,
                    ],
                }),
                new iam.PolicyStatement({
                    effect: iam.Effect.ALLOW,
                    actions: ['logs:CreateLogStream', 'logs:PutLogEvents'],
                    resources: [
                        `arn:aws:logs:${region}:${accountId}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*`,
                    ],
                }),
                new iam.PolicyStatement({
                    sid: 'ECRTokenAccess',
                    effect: iam.Effect.ALLOW,
                    actions: ['ecr:GetAuthorizationToken'],
                    resources: ['*'],
                }),
                new iam.PolicyStatement({
                    effect: iam.Effect.ALLOW,
                    actions: [
                        'xray:PutTraceSegments',
                        'xray:PutTelemetryRecords',
                        'xray:GetSamplingRules',
                        'xray:GetSamplingTargets',
                    ],
                resources: ['*'],
                }),
                new iam.PolicyStatement({
                    effect: iam.Effect.ALLOW,
                    actions: ['cloudwatch:PutMetricData'],
                    resources: ['*'],
                    conditions: {
                        StringEquals: { 'cloudwatch:namespace': 'bedrock-agentcore' },
                    },
                }),
                new iam.PolicyStatement({
                    sid: 'GetAgentAccessToken',
                    effect: iam.Effect.ALLOW,
                    actions: [
                        'bedrock-agentcore:GetWorkloadAccessToken',
                        'bedrock-agentcore:GetWorkloadAccessTokenForJWT',
                        'bedrock-agentcore:GetWorkloadAccessTokenForUserId',
                    ],
                    resources: [
                        `arn:aws:bedrock-agentcore:${region}:${accountId}:workload-identity-directory/default`,
                        `arn:aws:bedrock-agentcore:${region}:${accountId}:workload-identity-directory/default/workload-identity/agentName-*`,
                    ],
                }),
                new iam.PolicyStatement({
                    sid: 'BedrockModelInvocation',
                    effect: iam.Effect.ALLOW,
                    actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
                    resources: [
                        `arn:aws:bedrock:*::foundation-model/*`,
                        `arn:aws:bedrock:${region}:${accountId}:*`,
                    ],
                }),
            ],
        });

        const runtimeRole = new iam.Role(this, `${props.appName}-AgentCoreRuntimeRole`, {
            assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
            description: 'IAM role for Bedrock AgentCore Runtime',
            inlinePolicies: {
                RuntimeAccessPolicy: runtimePolicy
            }
        });

        this.agentCoreRuntime = new bedrockagentcore.CfnRuntime(this, `${props.appName}-AgentCoreRuntime`, {
            agentRuntimeArtifact: {
                containerConfiguration: {
                    containerUri: props.imageUri
                }
            },
            agentRuntimeName: "create_agent",
            protocolConfiguration: "HTTP",
            networkConfiguration: {
                networkMode: "PUBLIC"
            },
            roleArn: runtimeRole.roleArn,
            environmentVariables: {
                "GATEWAY_URL": this.agentCoreGateway.attrGatewayUrl,
                "MEMORY_ID":  this.agentCoreMemory.attrMemoryId,
                "COGNITO_CLIENT_ID": cognitoAppClient.userPoolClientId,
                "COGNITO_CLIENT_SECRET": cognitoAppClient.userPoolClientSecret.unsafeUnwrap(), // alternatives to consider: agentcore identity (no cdk constructs yet) or secrets manager
                "COGNITO_TOKEN_URL": cognitoTokenUrl,
                "COGNITO_SCOPE": `${cognitoResourceServer.userPoolResourceServerId}/${cognitoResourceServerScope.scopeName}`
            }
        });

        // DEFAULT endpoint always points to newest published version. Optionally, can use these versioned endpoints below
        // https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agent-runtime-versioning.html
        void new bedrockagentcore.CfnRuntimeEndpoint(this, `${props.appName}-AgentCoreRuntimeProdEndpoint`, {
            agentRuntimeId: this.agentCoreRuntime.attrAgentRuntimeId,
            agentRuntimeVersion: "1",
            name: "PROD"
        });

        void new bedrockagentcore.CfnRuntimeEndpoint(this, `${props.appName}-AgentCoreRuntimeDevEndpoint`, {
            agentRuntimeId: this.agentCoreRuntime.attrAgentRuntimeId,
            agentRuntimeVersion: "1",
            name: "DEV"
        });
    }
}

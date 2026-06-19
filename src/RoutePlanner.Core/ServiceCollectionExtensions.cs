using Microsoft.Extensions.DependencyInjection;
using RoutePlanner.Core.Configuration;
using RoutePlanner.Core.Routing;
using RoutePlanner.Core.Services;

namespace RoutePlanner.Core;

public static class ServiceCollectionExtensions
{
    public static IServiceCollection AddRoutePlanner(this IServiceCollection services, Action<PlannerOptions>? configure = null)
    {
        var options = new PlannerOptions();
        configure?.Invoke(options);
        services.AddSingleton(options);

        services.AddHttpClient<OsrmClient>((sp, client) =>
        {
            var opts = sp.GetRequiredService<PlannerOptions>();
            client.Timeout = TimeSpan.FromSeconds(opts.RequestTimeoutSeconds);
            client.DefaultRequestHeaders.UserAgent.ParseAdd("route-planner-dotnet/1.0");
            client.BaseAddress = new Uri(opts.OsrmBaseUrl.TrimEnd('/') + "/");
        });

        services.AddTransient<RoutePlannerService>();
        return services;
    }
}
